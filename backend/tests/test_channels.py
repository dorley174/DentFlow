"""Real engine / DB channel checks. Telegram network is replaced with a stub."""
import asyncio
from datetime import timedelta
from sqlalchemy import select, func
from fastapi import HTTPException
import pytest
from app import models as m
from app.db import SessionLocal, utcnow
from app.telegram_bot import process_update
from app import worker
from tests.conftest import clinic_and_slot, booking_payload, login


def web_booking(client):
    _, service, doctor, slot = clinic_and_slot(client)
    response = client.post('/api/public/clinics/smile-avenue/appointments', json=booking_payload(service, doctor, slot))
    assert response.status_code == 201, response.text
    return response.json()


def test_web_telegram_link_one_use_and_no_phone_matching(client, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    booked = web_booking(client)
    response = client.post('/api/public/clinics/smile-avenue/telegram-link', json={})
    assert response.status_code == 200, response.text
    command = response.json()['command']
    result = process_update(1234567, 100, command)
    assert 'связан' in result['text']
    with SessionLocal() as db:
        conv = db.scalar(select(m.Conversation).where(m.Conversation.external_id == '1234567'))
        assert conv.patient_id == booked['patient']['id']
    assert process_update(1234567, 100, command) is None  # same update replay
    with pytest.raises(HTTPException) as error:
        process_update(1234567, 101, command)
    assert error.value.status_code == 400  # token replay, new update
    result = process_update(1234567, 102, '/appointments')
    assert 'записан' in result['text']


def test_link_cannot_cross_tenant(client, monkeypatch):
    web_booking(client)
    command = client.post('/api/public/clinics/smile-avenue/telegram-link', json={}).json()['command']
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'aurora-dental')
    with pytest.raises(HTTPException) as error:
        process_update(7654321, 200, command)
    assert error.value.status_code == 400


def test_telegram_link_expires_with_source_session(client, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    web_booking(client)
    command = client.post('/api/public/clinics/smile-avenue/telegram-link', json={}).json()['command']
    with SessionLocal() as db:
        link = db.scalar(select(m.ChannelLink).where(m.ChannelLink.consumed_at.is_(None)))
        session = db.get(m.AuthSession, link.session_id)
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    with pytest.raises(HTTPException) as error:
        process_update(828282, 300, command)
    assert error.value.status_code == 400


def test_queued_marketing_is_suppressed_at_delivery_after_optout(client, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    booked = web_booking(client)
    command = client.post('/api/public/clinics/smile-avenue/telegram-link', json={}).json()['command']
    process_update(838383, 400, command)
    with SessionLocal() as db:
        patient = db.get(m.Patient, booked['patient']['id'])
        patient.marketing_enabled = False
        notification = m.Notification(tenant_id=patient.tenant_id, patient_id=patient.id,
            title='Marketing fixture', text='Synthetic', channel='telegram', status='pending', dedup_key='reactivation:fixture')
        db.add(notification); db.commit()
        notification_id = notification.id
    assert worker.claim_notification() == {'skip': True}
    with SessionLocal() as db:
        assert db.get(m.Notification, notification_id).status == 'suppressed'


def test_telegram_uses_same_guided_booking_engine(client, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    chat_id, update = 232323, 1000
    result = process_update(chat_id, update, '/book')
    for action in ['select_service', 'select_branch', 'select_doctor', 'select_slot']:
        index = next(i for i, opt in enumerate(result['options']) if opt['action'] == action)
        update += 1
        callback = f"df:{result['nonce']}:{index}"
        result = process_update(chat_id, update, callback=callback)
    update += 1
    result = process_update(chat_id, update, 'Тестовый Телеграм, +70000000888')
    index = next(i for i, opt in enumerate(result['options']) if opt['action'] == 'confirm_booking')
    update += 1
    result = process_update(chat_id, update, callback=f"df:{result['nonce']}:{index}")
    assert 'Запись подтверждена системой' in result['text']
    login(client)
    data = client.get('/api/admin/bootstrap').json()
    assert any(a['source'] == 'telegram' and a['patient_name'] == 'Тестовый Телеграм' for a in data['appointments'])


def test_stale_telegram_buttons_rejected(monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    first = process_update(101010, 1, '/book')
    process_update(101010, 2, '/help')
    with pytest.raises(HTTPException) as error:
        process_update(101010, 3, callback=f"df:{first['nonce']}:0")
    assert error.value.status_code == 409


def test_telegram_delivery_failure_never_marked_delivered(client, monkeypatch):
    monkeypatch.setenv('TELEGRAM_CLINIC_SLUG', 'smile-avenue')
    booked = web_booking(client)
    command = client.post('/api/public/clinics/smile-avenue/telegram-link', json={}).json()['command']
    process_update(121212, 1, command)
    with SessionLocal() as db:
        patient = db.get(m.Patient, booked['patient']['id'])
        worker.enqueue_booking_notifications(db, patient.tenant_id)
        db.commit()
    class Forbidden(Exception): pass
    class FakeBot:
        def __init__(self, token): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
        async def send_message(self, **kwargs): raise Forbidden()
    monkeypatch.setattr(worker, 'Bot', FakeBot)
    monkeypatch.setattr(worker, 'TelegramForbiddenError', Forbidden)
    monkeypatch.setenv('TELEGRAM_ENABLED', 'true')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'synthetic-no-network')
    assert asyncio.run(worker.deliver_pending()) == 0
    with SessionLocal() as db:
        notifications = list(db.scalars(select(m.Notification).where(m.Notification.patient_id == booked['patient']['id'], m.Notification.channel == 'telegram')))
        assert notifications and all(n.status == 'failed' and n.sent_at is None for n in notifications)
