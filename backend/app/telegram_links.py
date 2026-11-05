"""One-use channel linking, bound to the current verified browser capability."""
import os
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import models as m
from .db import get_db, utcnow, aware
from .security import visitor_session, optional_user, token_hash
from .services.booking import identity_patient
from .services.common import tenant_by_slug, audit

router = APIRouter(prefix='/api/public/clinics', tags=['Привязка Telegram'])

@router.post('/{slug}/telegram-link')
def create_link(slug: str, request: Request, response: Response, db: Session = Depends(get_db)):
    tenant = tenant_by_slug(db, slug)
    visitor = visitor_session(request, response, db)
    patient = identity_patient(db, tenant, visitor, optional_user(request, db), create=False)
    if not patient or patient.deleted_at:
        raise HTTPException(409, 'Сначала создайте запись в этом браузере или войдите под своим аккаунтом пациента')
    # Invalidate older unused links from this session before creating a new one.
    for old in db.scalars(select(m.ChannelLink).where(m.ChannelLink.tenant_id == tenant.id,
            m.ChannelLink.session_id == visitor.id, m.ChannelLink.consumed_at.is_(None))):
        old.consumed_at = utcnow()
    token = secrets.token_urlsafe(24)
    expires = utcnow() + timedelta(minutes=10)
    db.add(m.ChannelLink(tenant_id=tenant.id, token_hash=token_hash(token), session_id=visitor.id,
                         patient_id=patient.id, expires_at=expires))
    audit(db, tenant.id, None, 'channel.link_requested', 'patient', patient.id)
    db.commit()
    username = os.getenv('TELEGRAM_BOT_USERNAME', '').lstrip('@')
    return {'command': '/start link_' + token,
            'url': f'https://t.me/{username}?start=link_{token}' if username else None,
            'expires_at': expires.isoformat(), 'note': 'Одноразовая привязка. Не передавайте ссылку другим людям.'}


def consume_link(db, tenant, conversation, raw_token: str):
    if not (20 <= len(raw_token) <= 64):
        raise HTTPException(400, 'Неверный код привязки')
    link = db.scalar(select(m.ChannelLink).where(m.ChannelLink.tenant_id == tenant.id,
        m.ChannelLink.token_hash == token_hash(raw_token)).with_for_update())
    if not link or link.consumed_at or aware(link.expires_at) <= utcnow():
        raise HTTPException(400, 'Ссылка использована или устарела. Создайте новую на сайте клиники.')
    source_session = db.get(m.AuthSession, link.session_id)
    if not source_session or source_session.kind != 'visitor' or aware(source_session.expires_at) <= utcnow():
        raise HTTPException(400, 'Сессия сайта завершена. Войдите на сайт и создайте новую ссылку.')
    patient = db.scalar(select(m.Patient).where(m.Patient.id == link.patient_id,
        m.Patient.tenant_id == tenant.id, m.Patient.deleted_at.is_(None)))
    if not patient:
        raise HTTPException(400, 'Профиль недоступен')
    if conversation.patient_id and conversation.patient_id != patient.id:
        raise HTTPException(409, 'Этот Telegram уже связан с другим профилем. Обратитесь в клинику; автоматического объединения нет.')
    conversation.patient_id = patient.id
    if conversation.session_id:
        relation = db.scalar(select(m.VisitorPatient).where(m.VisitorPatient.tenant_id == tenant.id,
            m.VisitorPatient.session_id == conversation.session_id))
        if relation and relation.patient_id != patient.id:
            raise HTTPException(409, 'Нельзя перепривязать чужую сессию')
        if not relation:
            db.add(m.VisitorPatient(tenant_id=tenant.id, session_id=conversation.session_id, patient_id=patient.id))
    link.consumed_at = utcnow()
    audit(db, tenant.id, None, 'channel.linked', 'patient', patient.id)
    return patient
