"""Transactional booking. All writers lock the doctor before testing overlap.

PostgreSQL migration also installs a GiST exclusion constraint as defense in depth.
Caller owns commit. No network I/O runs inside this transaction.
"""
from datetime import datetime, date, time, timedelta, timezone
from hashlib import sha256
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import models as m
from ..db import utcnow, aware
from .common import tenant_item, audit

ACTIVE_STATUSES = ['scheduled', 'confirmed', 'completed']


def identity_patient(db: Session, tenant: m.Tenant, visitor: m.AuthSession, user=None,
                     name=None, phone=None, notifications=False, create=False):
    # Serialize first-time submissions for the same visitor identity.
    if create:
        db.scalar(select(m.AuthSession).where(m.AuthSession.id == visitor.id).with_for_update())
    if user and user.role == 'patient' and user.tenant_id == tenant.id and user.patient_id:
        patient = tenant_item(db, m.Patient, user.patient_id, tenant.id)
        if patient.deleted_at:
            raise HTTPException(410, 'Данные этого профиля удалены')
        return patient
    link = db.scalar(select(m.VisitorPatient).where(m.VisitorPatient.tenant_id == tenant.id,
                                                   m.VisitorPatient.session_id == visitor.id))
    if link:
        return tenant_item(db, m.Patient, link.patient_id, tenant.id)
    if not create:
        return None
    patient = m.Patient(tenant_id=tenant.id, name=name, phone=phone,
                        notifications_enabled=notifications, segment='Новый пациент')
    db.add(patient)
    db.flush()
    db.add(m.VisitorPatient(tenant_id=tenant.id, session_id=visitor.id, patient_id=patient.id))
    db.flush()
    return patient


def save_consents(db, tenant_id, patient, consent_pd=True, notifications=False, source='web'):
    if not consent_pd:
        raise HTTPException(422, 'Для записи необходимо согласие на обработку данных')
    db.add(m.ConsentRecord(tenant_id=tenant_id, patient_id=patient.id, purpose='booking', granted=True, source=source))
    db.add(m.ConsentRecord(tenant_id=tenant_id, patient_id=patient.id, purpose='notifications', granted=notifications, source=source))
    patient.notifications_enabled = notifications


def _entities(db, tenant_id, service_id, doctor_id, branch_id, lock=False):
    service = tenant_item(db, m.Service, service_id, tenant_id)
    query = select(m.Doctor).where(m.Doctor.id == doctor_id, m.Doctor.tenant_id == tenant_id)
    doctor = db.scalar(query.with_for_update() if lock else query)
    branch = tenant_item(db, m.Branch, branch_id, tenant_id)
    if not doctor or not doctor.active or not service.active or not branch.active:
        raise HTTPException(404, 'Врач, услуга или филиал недоступны')
    if doctor.branch_id != branch.id:
        raise HTTPException(422, 'Врач не принимает в выбранном филиале')
    association = db.scalar(select(m.DoctorService.id).where(m.DoctorService.tenant_id == tenant_id,
        m.DoctorService.doctor_id == doctor_id, m.DoctorService.service_id == service_id))
    if not association:
        raise HTTPException(422, 'Врач не оказывает выбранную услугу')
    return service, doctor, branch


def _inside_schedule(db, tenant, doctor_id, branch_id, start_at, end_at):
    local_start = aware(start_at).astimezone(ZoneInfo(tenant.timezone))
    local_end = aware(end_at).astimezone(ZoneInfo(tenant.timezone))
    schedule = db.scalar(select(m.Schedule).where(m.Schedule.tenant_id == tenant.id,
        m.Schedule.doctor_id == doctor_id, m.Schedule.branch_id == branch_id,
        m.Schedule.weekday == local_start.weekday(), m.Schedule.active.is_(True)))
    if not schedule or local_start.date() != local_end.date():
        return False
    st, en = local_start.strftime('%H:%M'), local_end.strftime('%H:%M')
    if st < schedule.start_time or en > schedule.end_time:
        return False
    if schedule.break_start and schedule.break_end and st < schedule.break_end and en > schedule.break_start:
        return False
    return not (local_start.second or local_start.microsecond or local_start.minute % 15)


def _conflict(db, tenant_id, doctor_id, start_at, end_at, ignore_id=None):
    query = select(m.Appointment.id).where(m.Appointment.tenant_id == tenant_id,
        m.Appointment.doctor_id == doctor_id, m.Appointment.status.in_(ACTIVE_STATUSES),
        m.Appointment.start_at < end_at, m.Appointment.end_at > start_at)
    if ignore_id:
        query = query.where(m.Appointment.id != ignore_id)
    return db.scalar(query.limit(1)) is not None


def available_slots(db: Session, tenant: m.Tenant, service_id: str, day: date,
                    doctor_id: str | None = None, branch_id: str | None = None) -> list[dict]:
    service = tenant_item(db, m.Service, service_id, tenant.id)
    if not service.active:
        return []
    local_today = utcnow().astimezone(ZoneInfo(tenant.timezone)).date()
    if day < local_today or day > local_today + timedelta(days=180):
        return []
    query = select(m.Doctor).join(m.DoctorService, m.DoctorService.doctor_id == m.Doctor.id).where(
        m.Doctor.tenant_id == tenant.id, m.DoctorService.tenant_id == tenant.id,
        m.DoctorService.service_id == service_id, m.Doctor.active.is_(True))
    if doctor_id:
        tenant_item(db, m.Doctor, doctor_id, tenant.id)
        query = query.where(m.Doctor.id == doctor_id)
    if branch_id:
        tenant_item(db, m.Branch, branch_id, tenant.id)
        query = query.where(m.Doctor.branch_id == branch_id)
    result = []
    tz = ZoneInfo(tenant.timezone)
    for doctor in db.scalars(query.order_by(m.Doctor.name)).unique():
        branch = db.get(m.Branch, doctor.branch_id)
        if not branch.active:
            continue
        schedule = db.scalar(select(m.Schedule).where(m.Schedule.tenant_id == tenant.id,
            m.Schedule.doctor_id == doctor.id, m.Schedule.weekday == day.weekday(), m.Schedule.active.is_(True)))
        if not schedule:
            continue
        start = datetime.combine(day, time.fromisoformat(schedule.start_time), tzinfo=tz)
        finish = datetime.combine(day, time.fromisoformat(schedule.end_time), tzinfo=tz)
        appointments = list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id == tenant.id,
            m.Appointment.doctor_id == doctor.id, m.Appointment.status.in_(ACTIVE_STATUSES),
            m.Appointment.start_at < finish, m.Appointment.end_at > start)))
        while start + timedelta(minutes=service.duration_minutes) <= finish:
            end = start + timedelta(minutes=service.duration_minutes)
            if start > utcnow() and _inside_schedule(db, tenant, doctor.id, doctor.branch_id, start, end) and not any(
                aware(a.start_at) < end and aware(a.end_at) > start for a in appointments):
                result.append({'start_at':start.isoformat(),'end_at':end.isoformat(),
                               'doctor_id':doctor.id,'doctor_name':doctor.name,'branch_id':doctor.branch_id})
            start += timedelta(minutes=15)
    return sorted(result, key=lambda x: (x['start_at'], x['doctor_name']))[:500]


def upsert_lead(db, tenant_id, patient_id, title, stage, source='web', amount=0, conversation_id=None):
    lead = db.scalar(select(m.Lead).where(m.Lead.tenant_id == tenant_id, m.Lead.patient_id == patient_id))
    conversation_lead = db.scalar(select(m.Lead).where(m.Lead.tenant_id == tenant_id,
        m.Lead.conversation_id == conversation_id)) if conversation_id else None
    if not lead:
        lead = conversation_lead or m.Lead(tenant_id=tenant_id, patient_id=patient_id, source=source)
        db.add(lead)
    elif conversation_lead and conversation_lead.id != lead.id:
        # Same proven visitor identity: converge chat and booking lead, never merge by phone.
        db.delete(conversation_lead)
        db.flush()
    lead.patient_id = patient_id
    if conversation_id:
        lead.conversation_id = conversation_id
    lead.title, lead.stage, lead.amount_kopecks = title, stage, amount
    lead.summary = f'{title}. Статус: {stage}.'
    return lead


def notify(db, appointment, title, text, kind):
    timestamp = aware(appointment.start_at).isoformat()
    # In-app is an actual durable delivery channel; external sends are worker-controlled.
    db.add(m.Notification(tenant_id=appointment.tenant_id, patient_id=appointment.patient_id,
        appointment_id=appointment.id, title=title, text=text, channel='in_app', status='delivered',
        sent_at=utcnow(), dedup_key=None))


def create_appointment(db: Session, tenant: m.Tenant, patient: m.Patient, service_id: str,
                       doctor_id: str, branch_id: str, start_at: datetime,
                       idempotency_key: str, identity_id: str, source='web', actor_id=None,
                       conversation_id=None) -> m.Appointment:
    if patient.tenant_id != tenant.id or patient.deleted_at:
        raise HTTPException(404, 'Пациент не найден')
    key = sha256(f'{identity_id}:{idempotency_key}'.encode()).hexdigest()
    service, doctor, branch = _entities(db, tenant.id, service_id, doctor_id, branch_id, lock=True)
    existing = db.scalar(select(m.Appointment).where(m.Appointment.tenant_id == tenant.id,
        m.Appointment.idempotency_key == key))
    if existing:
        if existing.patient_id != patient.id or existing.doctor_id != doctor_id or existing.service_id != service_id or aware(existing.start_at) != aware(start_at):
            raise HTTPException(409, 'Этот ключ запроса уже использован для другой записи')
        return existing
    start_at = aware(start_at).astimezone(timezone.utc)
    end_at = start_at + timedelta(minutes=service.duration_minutes)
    if start_at <= utcnow() or start_at > utcnow() + timedelta(days=180):
        raise HTTPException(422, 'Выберите будущую дату в пределах 180 дней')
    if not _inside_schedule(db, tenant, doctor.id, branch.id, start_at, end_at):
        raise HTTPException(409, 'Это время находится вне рабочего расписания или попадает на перерыв')
    if _conflict(db, tenant.id, doctor.id, start_at, end_at):
        raise HTTPException(409, 'Это время уже занято. Выберите другой свободный интервал.')
    appointment = m.Appointment(tenant_id=tenant.id, patient_id=patient.id, service_id=service.id,
        doctor_id=doctor.id, branch_id=branch.id, start_at=start_at, end_at=end_at,
        price_kopecks=service.price_kopecks, source=source, idempotency_key=key)
    db.add(appointment)
    db.flush()
    upsert_lead(db, tenant.id, patient.id, service.name, 'Записан', source, service.price_kopecks, conversation_id)
    notify(db, appointment, 'Запись создана', 'Запись на приём сохранена. Время можно проверить в личном кабинете.', 'created')
    audit(db, tenant.id, actor_id, 'appointment.created', 'appointment', appointment.id,
          {'source':source,'doctor_id':doctor.id})
    return appointment


def change_appointment(db: Session, tenant: m.Tenant, appointment: m.Appointment,
                       action=None, status=None, start_at=None, actor_id=None):
    if appointment.tenant_id != tenant.id:
        raise HTTPException(404, 'Запись не найдена')
    # Same lock order as create_appointment; row lock refreshes status after waiting.
    db.scalar(select(m.Doctor).where(m.Doctor.id == appointment.doctor_id,
                                    m.Doctor.tenant_id == tenant.id).with_for_update())
    db.refresh(appointment)
    old_status = appointment.status
    target = status or {'cancel':'cancelled','confirm':'confirmed'}.get(action)
    if start_at is not None:
        if old_status in {'cancelled','completed','no_show'}:
            raise HTTPException(409, 'Нельзя перенести закрытую запись; создайте новую')
        start_at = aware(start_at).astimezone(timezone.utc)
        if start_at <= utcnow() or start_at > utcnow() + timedelta(days=180):
            raise HTTPException(422, 'Выберите будущую дату в пределах 180 дней')
        duration = aware(appointment.end_at) - aware(appointment.start_at)
        end_at = start_at + duration
        if not _inside_schedule(db, tenant, appointment.doctor_id, appointment.branch_id, start_at, end_at):
            raise HTTPException(409, 'Время вне расписания или попадает на перерыв')
        if _conflict(db, tenant.id, appointment.doctor_id, start_at, end_at, appointment.id):
            raise HTTPException(409, 'Новое время уже занято')
        if aware(appointment.start_at) != start_at:
            appointment.start_at, appointment.end_at, appointment.status = start_at, end_at, 'scheduled'
            notify(db, appointment, 'Запись перенесена', 'Время приёма изменено. Проверьте новое время в личном кабинете.', 'rescheduled')
    if target:
        if old_status in {'cancelled','completed','no_show'} and target != old_status:
            raise HTTPException(409, 'Закрытую запись нельзя вернуть в расписание')
        if target != appointment.status:
            appointment.status = target
            labels = {'cancelled':'Запись отменена','confirmed':'Запись подтверждена',
                      'completed':'Приём завершён','no_show':'Визит не состоялся'}
            notify(db, appointment, labels.get(target, 'Статус записи изменён'), 'Изменение сохранено в личном кабинете.', 'status')
    stage = {'scheduled':'Записан','confirmed':'Подтверждён','completed':'Посетил','cancelled':'Потерян','no_show':'Потерян'}
    lead = db.scalar(select(m.Lead).where(m.Lead.tenant_id == tenant.id, m.Lead.patient_id == appointment.patient_id))
    if lead:
        lead.stage = stage[appointment.status]
    audit(db, tenant.id, actor_id, 'appointment.updated', 'appointment', appointment.id,
          {'previous_status':old_status,'status':appointment.status})
    db.flush()
    return appointment
