from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import models as m, schemas as s
from ..db import get_db, utcnow
from ..security import DUMMY_HASH, verify_password, issue_session, read_session, current_user, public_user, AUTH_COOKIE, VISITOR_COOKIE

router=APIRouter(prefix='/api/auth',tags=['Авторизация'])


@router.post('/login')
def login(data:s.LoginInput,request:Request,response:Response,db:Session=Depends(get_db)):
    user=db.scalar(select(m.User).where(m.User.email==data.email.lower()))
    valid=verify_password(data.password,user.password_hash if user else DUMMY_HASH)
    tenant=db.get(m.Tenant,user.tenant_id) if user and user.tenant_id else None
    if not user or not valid or not user.active or (tenant and tenant.status!='active'):
        raise HTTPException(401,'Неверный логин или пароль, либо доступ временно закрыт')
    previous=read_session(request,db)
    if previous:
        db.delete(previous)
    issue_session(db,response,user.id)
    if user.role=='patient':
        # A patient account receives a separate browser capability, never a previous
        # account's or anonymous guest's identity based on unverified phone matching.
        issue_session(db,response,kind='visitor')
    db.commit()
    return {'user':public_user(user)}


@router.get('/me')
def me(user=Depends(current_user)):
    return {'user':public_user(user)}


@router.post('/logout')
def logout(request:Request,response:Response,db:Session=Depends(get_db)):
    session=read_session(request,db)
    if session:
        user=db.get(m.User,session.user_id) if session.user_id else None
        if user and user.role=='patient':
            visitor=read_session(request,db,'visitor')
            if visitor:
                visitor.expires_at=utcnow()
                for link in db.scalars(select(m.ChannelLink).where(m.ChannelLink.session_id==visitor.id,m.ChannelLink.consumed_at.is_(None))):
                    link.consumed_at=utcnow()
            response.delete_cookie(VISITOR_COOKIE,path='/')
        db.delete(session)
    response.delete_cookie(AUTH_COOKIE,path='/')
    db.commit()
    return {'message':'Вы вышли из аккаунта'}
