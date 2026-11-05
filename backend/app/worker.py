"""Durable PostgreSQL outbox + Redis leadership, a simple Celery alternative.

Delivery is at-least-once: a crash after Telegram accepts but before DB commit
can repeat a generic notification. Booking itself remains transactional/idempotent.
"""
import asyncio
import logging
import os
import signal
import time
from datetime import timedelta
from sqlalchemy import select, update
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramForbiddenError
from . import models as m
from .config import settings
from .db import SessionLocal, utcnow, aware
from .services.automations import run_automations

log = logging.getLogger('dentflow.worker')
stopping = False


def enqueue_booking_notifications(db, tenant_id):
    candidates = db.scalars(select(m.Notification).where(m.Notification.tenant_id == tenant_id,
        m.Notification.channel == 'in_app', m.Notification.appointment_id.is_not(None),
        m.Notification.created_at > utcnow() - timedelta(days=2)).order_by(m.Notification.created_at).limit(500))
    count = 0
    for source in candidates:
        patient = db.get(m.Patient, source.patient_id) if source.patient_id else None
        if not patient or not patient.notifications_enabled or patient.deleted_at:
            continue
        linked = db.scalar(select(m.Conversation.id).where(m.Conversation.tenant_id == tenant_id,
            m.Conversation.patient_id == patient.id, m.Conversation.channel == 'telegram', m.Conversation.external_id.is_not(None)))
        if not linked:
            continue
        key = 'tg:' + source.id
        if not db.scalar(select(m.Notification.id).where(m.Notification.tenant_id == tenant_id, m.Notification.dedup_key == key)):
            db.add(m.Notification(tenant_id=tenant_id, patient_id=patient.id, appointment_id=source.appointment_id,
                title=source.title, text='В записи на приём есть обновление. Проверьте детали командой /appointments или на сайте клиники.',
                channel='telegram', status='pending', dedup_key=key))
            count += 1
    return count


def run_once():
    counts = {'tenants': 0, 'notifications': 0, 'tasks': 0}
    with SessionLocal() as db:
        ids = list(db.scalars(select(m.Tenant.id).where(m.Tenant.status == 'active')))
    for tenant_id in ids:
        with SessionLocal() as db:
            result = run_automations(db, tenant_id)
            counts['notifications'] += result['notifications_created'] + enqueue_booking_notifications(db, tenant_id)
            counts['tasks'] += result['tasks_created']
            counts['tenants'] += 1
            db.commit()
    return counts


def claim_notification():
    with SessionLocal() as db:
        now = utcnow()
        # Recover expired leases, retaining attempts and unique dedup keys.
        db.execute(update(m.Notification).where(m.Notification.channel.in_(['telegram', 'telegram_reply']),
            m.Notification.status == 'sending', m.Notification.scheduled_at <= now).values(status='pending'))
        n = db.scalar(select(m.Notification).where(m.Notification.channel.in_(['telegram', 'telegram_reply']),
            m.Notification.status == 'pending', m.Notification.scheduled_at <= now,
            m.Notification.attempts < 5).order_by(m.Notification.created_at).with_for_update(skip_locked=True).limit(1))
        if not n:
            db.commit()
            return None
        tenant = db.get(m.Tenant, n.tenant_id)
        patient = db.get(m.Patient, n.patient_id) if n.patient_id else None
        is_reply = n.channel == 'telegram_reply'
        if is_reply:
            message_id = (n.dedup_key or '').removeprefix('staff:')
            message = db.scalar(select(m.Message).where(m.Message.id == message_id,
                m.Message.tenant_id == n.tenant_id, m.Message.role == 'staff'))
            conv = db.scalar(select(m.Conversation).where(m.Conversation.id == message.conversation_id,
                m.Conversation.tenant_id == n.tenant_id, m.Conversation.channel == 'telegram',
                m.Conversation.external_id.is_not(None))) if message else None
        else:
            conv = db.scalar(select(m.Conversation).where(m.Conversation.tenant_id == n.tenant_id,
                m.Conversation.patient_id == n.patient_id, m.Conversation.channel == 'telegram',
                m.Conversation.external_id.is_not(None)))
        marketing_opt_out = (n.dedup_key or '').startswith('reactivation:') and (not patient or not patient.marketing_enabled)
        no_consent = not is_reply and (not patient or patient.deleted_at or not patient.notifications_enabled or marketing_opt_out)
        if not tenant or tenant.status != 'active' or no_consent or not conv:
            n.status = 'suppressed'
            db.commit()
            return {'skip': True}
        # One worker token must never notify patients of another clinic.
        if tenant.slug != os.getenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue'):
            n.scheduled_at = now + timedelta(minutes=5)
            db.commit()
            return {'skip': True}
        n.status = 'sending'
        n.attempts += 1
        n.scheduled_at = now + timedelta(minutes=5)
        # Automatic bodies are generic; staff replies are explicit administrative
        # messages to the same verified chat, never a contact matched by phone.
        result = {'id': n.id, 'chat_id': conv.external_id, 'text': f'{tenant.name}\n{n.title}\n{n.text}'[:4000]}
        db.commit()
        return result


def complete_notification(item_id, status, retry_seconds=60):
    with SessionLocal() as db:
        n = db.get(m.Notification, item_id)
        if n and n.status == 'sending':
            n.status = 'failed' if n.attempts >= 5 and status == 'pending' else status
            n.scheduled_at = utcnow() + timedelta(seconds=max(1, min(retry_seconds, 3600)))
            if status == 'delivered':
                n.sent_at = utcnow()
            db.commit()


async def deliver_pending(limit=10):
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    if not token or os.getenv('TELEGRAM_ENABLED', 'false').lower() != 'true':
        return 0
    delivered = 0
    async with Bot(token) as bot:
        for _ in range(limit):
            item = await asyncio.to_thread(claim_notification)
            if not item:
                break
            if item.get('skip'):
                continue
            try:
                await bot.send_message(chat_id=item['chat_id'], text=item['text'], request_timeout=10)
                await asyncio.to_thread(complete_notification, item['id'], 'delivered')
                delivered += 1
            except TelegramRetryAfter as exc:
                await asyncio.to_thread(complete_notification, item['id'], 'pending', exc.retry_after)
            except TelegramForbiddenError:
                await asyncio.to_thread(complete_notification, item['id'], 'failed')
            except TelegramAPIError:
                await asyncio.to_thread(complete_notification, item['id'], 'pending', 120)
                log.warning('notification_delivery_failed')
    return delivered


def stop(signum, frame):
    global stopping
    stopping = True


def main():
    import redis
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    client = redis.Redis.from_url(settings.redis_url, socket_timeout=3, socket_connect_timeout=3) if settings.redis_url else None
    if not client and settings.app_env == 'production':
        raise SystemExit('В production worker требует Redis')
    while not stopping:
        lock = client.lock('dentflow:automation-worker', timeout=180, blocking=False) if client else None
        acquired = False
        try:
            acquired = lock.acquire(blocking=False) if lock else True
            if acquired:
                run_once()
                asyncio.run(deliver_pending())
                if client:
                    client.set('dentflow:worker:last_tick', utcnow().isoformat(), ex=180)
        except Exception:
            log.error('worker_tick_failed')
        finally:
            if lock and acquired:
                try:
                    lock.release()
                except redis.exceptions.LockError:
                    log.warning('worker_lock_expired')
        for _ in range(30):
            if stopping:
                break
            time.sleep(1)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
    main()
