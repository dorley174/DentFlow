from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import models as m
from ..db import aware, utcnow


def tenant_item(db: Session, model, item_id: str, tenant_id: str):
    item = db.scalar(select(model).where(model.id == item_id, model.tenant_id == tenant_id))
    if not item:
        raise HTTPException(404, 'Запись не найдена')
    return item


def tenant_by_slug(db: Session, slug: str):
    tenant = db.scalar(select(m.Tenant).where(m.Tenant.slug == slug, m.Tenant.status == 'active'))
    if not tenant:
        raise HTTPException(404, 'Клиника не найдена или временно недоступна')
    return tenant


def audit(db, tenant_id, actor_id, action, entity_type, entity_id='', details=None):
    db.add(m.AuditLog(tenant_id=tenant_id, actor_id=actor_id, action=action,
                      entity_type=entity_type, entity_id=entity_id, details=details or {}))


def serial(item, db: Session | None = None) -> dict:
    if item is None:
        return {}
    omitted = {'password_hash', 'token_hash', 'context', 'session_id', 'external_id', 'idempotency_key'}
    data = {}
    for column in item.__table__.columns:
        if column.name in omitted:
            continue
        value = getattr(item, column.name)
        data[column.name] = aware(value).isoformat() if isinstance(value, datetime) else value
    if not db:
        return data
    if isinstance(item, m.Patient):
        visits=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==item.tenant_id,
            m.Appointment.patient_id==item.id,m.Appointment.status=='completed').order_by(m.Appointment.start_at.desc())))
        if not visits:
            data['segment']='Новый пациент'
        elif aware(visits[0].start_at)<utcnow()-timedelta(days=60):
            data['segment']='Не был более 60 дней'
        elif len(visits)==1:
            data['segment']='Первый визит'
        else:
            data['segment']='Постоянный'
        data['visits_count']=len(visits)
        data['last_visit_at']=aware(visits[0].start_at).isoformat() if visits else None
    if isinstance(item, m.Doctor):
        data['service_ids'] = list(db.scalars(select(m.DoctorService.service_id).where(
            m.DoctorService.tenant_id == item.tenant_id, m.DoctorService.doctor_id == item.id)))
    if isinstance(item, m.Appointment):
        for model, field, output in [(m.Patient,'patient_id','patient_name'),(m.Doctor,'doctor_id','doctor_name'),
                                     (m.Service,'service_id','service_name'),(m.Branch,'branch_id','branch_name')]:
            related = db.get(model, getattr(item, field))
            data[output] = related.name if related and related.tenant_id == item.tenant_id else ''
    if isinstance(item, (m.Lead, m.Task, m.Conversation)):
        patient = db.get(m.Patient, item.patient_id) if item.patient_id else None
        data['patient_name'] = patient.name if patient and patient.tenant_id == item.tenant_id else 'Гость'
    if isinstance(item, m.Conversation):
        last = db.scalar(select(m.Message).where(m.Message.tenant_id == item.tenant_id,
                                                m.Message.conversation_id == item.id).order_by(m.Message.created_at.desc()).limit(1))
        data['last_message'] = last.text if last else ''
    return data


def items(db, model, tenant_id, limit=1000):
    return list(db.scalars(select(model).where(model.tenant_id == tenant_id).order_by(model.created_at.desc()).limit(limit)))
