import hashlib
import hmac
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db, utcnow, aware
from .models import AuthSession, User, Tenant

AUTH_COOKIE = 'dentflow_session'
VISITOR_COOKIE = 'dentflow_visitor'
CLINIC_ROLES = {'owner', 'manager', 'administrator', 'doctor'}
EDIT_ROLES = {'owner', 'manager', 'administrator'}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 600000
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations).hex()
    return f'pbkdf2_sha256${iterations}${salt}${digest}'


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt, expected = stored.split('$')
        if algorithm != 'pbkdf2_sha256':
            return False
        result = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(result, expected)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password('unknown-user-timing-placeholder')


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def read_session(request: Request, db: Session, kind='auth') -> AuthSession | None:
    token = request.cookies.get(AUTH_COOKIE if kind == 'auth' else VISITOR_COOKIE)
    if not token or len(token) > 256:
        return None
    return db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token),
                                             AuthSession.kind == kind, AuthSession.expires_at > utcnow()))


def issue_session(db: Session, response: Response, user_id: str | None = None, kind='auth') -> AuthSession:
    token = secrets.token_urlsafe(32)
    seconds = settings.session_hours * 3600 if kind == 'auth' else settings.visitor_days * 86400
    session = AuthSession(token_hash=token_hash(token), user_id=user_id, kind=kind,
                          expires_at=utcnow() + timedelta(seconds=seconds))
    db.add(session)
    db.flush()
    response.set_cookie(AUTH_COOKIE if kind == 'auth' else VISITOR_COOKIE, token,
                        max_age=seconds, httponly=True, secure=settings.cookie_secure,
                        samesite='lax', path='/')
    return session


def visitor_session(request: Request, response: Response, db: Session) -> AuthSession:
    session = read_session(request, db, 'visitor')
    return session or issue_session(db, response, kind='visitor')


def optional_user(request: Request, db: Session) -> User | None:
    session = read_session(request, db)
    if not session or not session.user_id:
        return None
    user = db.get(User, session.user_id)
    if not user or not user.active:
        return None
    if user.tenant_id:
        tenant = db.get(Tenant, user.tenant_id)
        if not tenant or tenant.status != 'active':
            return None
    return user


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = optional_user(request, db)
    if not user:
        raise HTTPException(401, 'Войдите в аккаунт')
    return user


def clinic_user(user: User = Depends(current_user)) -> User:
    if user.role not in CLINIC_ROLES or not user.tenant_id:
        raise HTTPException(403, 'Доступ к кабинету клиники не разрешён')
    return user


def super_user(user: User = Depends(current_user)) -> User:
    if user.role != 'super_admin':
        raise HTTPException(403, 'Необходима роль владельца платформы')
    return user


def require_roles(user: User, allowed: set[str]):
    if user.role not in allowed:
        raise HTTPException(403, 'Для этого действия недостаточно прав')


def public_user(user: User) -> dict:
    return {k: getattr(user, k) for k in ['id','tenant_id','name','email','role','active','doctor_id','patient_id']}
