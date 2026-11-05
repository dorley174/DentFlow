"""Idempotent durable automation rules. A worker calls this on a schedule."""
from datetime import timedelta
from sqlalchemy import select
from .. import models as m
from ..db import utcnow, aware
from .common import audit


def _notification(db, tenant_id, patient, title, text, key, appointment=None, now=None):
    if not patient.notifications_enabled or patient.deleted_at:
        return False
    if db.scalar(select(m.Notification.id).where(m.Notification.tenant_id==tenant_id,m.Notification.dedup_key==key)):
        return False
    telegram = db.scalar(select(m.Conversation.id).where(m.Conversation.tenant_id==tenant_id,
        m.Conversation.patient_id==patient.id,m.Conversation.channel=='telegram',m.Conversation.external_id.is_not(None)))
    channel='telegram' if telegram else 'in_app'
    db.add(m.Notification(tenant_id=tenant_id,patient_id=patient.id,
        appointment_id=appointment.id if appointment else None,title=title,text=text,
        channel=channel,status='pending' if telegram else 'delivered',dedup_key=key,
        scheduled_at=now or utcnow(),sent_at=None if telegram else utcnow()))
    return True


def run_automations(db, tenant_id: str, now=None) -> dict:
    now = aware(now or utcnow())
    # Prevent concurrent workers from enqueuing the same work on one tenant.
    tenant=db.scalar(select(m.Tenant).where(m.Tenant.id==tenant_id,m.Tenant.status=='active').with_for_update())
    if not tenant:
        return {'notifications_created':0,'tasks_created':0,'evaluated_at':now.isoformat()}
    counts={'notifications_created':0,'tasks_created':0,'evaluated_at':now.isoformat()}
    rules=list(db.scalars(select(m.AutomationRule).where(m.AutomationRule.tenant_id==tenant_id,m.AutomationRule.enabled.is_(True))))
    for rule in rules:
        delay=timedelta(minutes=rule.delay_minutes)
        if rule.kind=='reminder':
            appointments=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==tenant_id,
                m.Appointment.status.in_(['scheduled','confirmed']),m.Appointment.start_at>now,m.Appointment.start_at<=now+delay)))
            for appointment in appointments:
                patient=db.get(m.Patient,appointment.patient_id)
                key=f'reminder:{rule.id}:{appointment.id}:{aware(appointment.start_at).isoformat()}'
                counts['notifications_created']+=int(_notification(db,tenant_id,patient,'Напоминание о визите',
                    'У вас запланирован визит. Проверьте дату и время в личном кабинете клиники.',key,appointment,now))
        elif rule.kind=='missed_reply':
            conversations=list(db.scalars(select(m.Conversation).where(m.Conversation.tenant_id==tenant_id,
                m.Conversation.status=='open',m.Conversation.updated_at<=now-delay)))
            for conversation in conversations:
                last=db.scalar(select(m.Message).where(m.Message.conversation_id==conversation.id,
                    m.Message.tenant_id==tenant_id).order_by(m.Message.created_at.desc()).limit(1))
                if not last or last.role not in {'assistant','staff'}:
                    continue
                if conversation.patient_id and db.scalar(select(m.Appointment.id).where(m.Appointment.tenant_id==tenant_id,
                        m.Appointment.patient_id==conversation.patient_id,m.Appointment.status.in_(['scheduled','confirmed']),m.Appointment.start_at>now)):
                    continue
                key=f'missed:{rule.id}:{conversation.id}:{last.id}'
                if not db.scalar(select(m.Task.id).where(m.Task.tenant_id==tenant_id,m.Task.dedup_key==key)):
                    db.add(m.Task(tenant_id=tenant_id,patient_id=conversation.patient_id,title='Связаться с пациентом',
                        description='Пациент не ответил на предложение в диалоге. Проверьте историю и предложенное время.',
                        due_at=now,dedup_key=key))
                    counts['tasks_created']+=1
        elif rule.kind=='feedback':
            appointments=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==tenant_id,
                m.Appointment.status=='completed',m.Appointment.end_at<=now-delay)))
            for appointment in appointments:
                patient=db.get(m.Patient,appointment.patient_id)
                counts['notifications_created']+=int(_notification(db,tenant_id,patient,'Как прошёл визит?',
                    'Поделитесь обратной связью в чате клиники. Ваше сообщение прочитает администратор.',
                    f'feedback:{rule.id}:{appointment.id}',appointment,now))
        elif rule.kind=='reactivation':
            patients=list(db.scalars(select(m.Patient).where(m.Patient.tenant_id==tenant_id,
                m.Patient.marketing_enabled.is_(True),m.Patient.notifications_enabled.is_(True),m.Patient.deleted_at.is_(None))))
            for patient in patients:
                latest=db.scalar(select(m.Appointment).where(m.Appointment.tenant_id==tenant_id,
                    m.Appointment.patient_id==patient.id,m.Appointment.status=='completed').order_by(m.Appointment.start_at.desc()).limit(1))
                future=db.scalar(select(m.Appointment.id).where(m.Appointment.tenant_id==tenant_id,
                    m.Appointment.patient_id==patient.id,m.Appointment.status.in_(['scheduled','confirmed']),m.Appointment.start_at>now))
                if latest and aware(latest.start_at)<=now-delay and not future:
                    counts['notifications_created']+=int(_notification(db,tenant_id,patient,'Связаться с клиникой',
                        'Если вы планируете новый визит, выберите удобное время на сайте клиники. Рассылку можно отключить в настройках согласий.',
                        f'reactivation:{rule.id}:{patient.id}:{latest.id}',now=now))
        elif rule.kind=='waitlist':
            # This explicit administrative task is the waitlist in the MVP; no unsolicited marketing.
            waiting=list(db.scalars(select(m.Task).where(m.Task.tenant_id==tenant_id,m.Task.status=='open',
                m.Task.title=='Лист ожидания')))
            for task in waiting:
                key=f'waitlist:{rule.id}:{task.id}'
                if not db.scalar(select(m.Task.id).where(m.Task.tenant_id==tenant_id,m.Task.dedup_key==key)):
                    db.add(m.Task(tenant_id=tenant_id,patient_id=task.patient_id,title='Проверить свободные интервалы',
                        description='Пациент в листе ожидания. Откройте расписание и согласуйте подходящее время.',due_at=now,dedup_key=key))
                    counts['tasks_created']+=1
    if counts['notifications_created'] or counts['tasks_created']:
        audit(db,tenant_id,None,'automations.run','automation',details=counts)
    db.flush()
    return counts
