"""This gate runs with PostgreSQL in CI. SQLite deliberately skips it."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, time
from threading import Barrier
from zoneinfo import ZoneInfo
import uuid
import pytest
from fastapi import HTTPException
from app.db import engine, Base, SessionLocal, utcnow
from app import models as m
from app.services.booking import create_appointment


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='Requires real PostgreSQL row locks and GiST exclusion')
def test_two_concurrent_requests_cannot_claim_same_interval():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        tenant = m.Tenant(name='Concurrency fixture', slug='ci-' + uuid.uuid4().hex)
        db.add(tenant); db.flush()
        branch = m.Branch(tenant_id=tenant.id, name='CI')
        db.add(branch); db.flush()
        doctor = m.Doctor(tenant_id=tenant.id, branch_id=branch.id, name='CI doctor')
        service = m.Service(tenant_id=tenant.id, name='CI service', duration_minutes=60, price_kopecks=10000)
        db.add_all([doctor, service]); db.flush()
        db.add(m.DoctorService(tenant_id=tenant.id, doctor_id=doctor.id, service_id=service.id))
        day = utcnow().astimezone(ZoneInfo('Europe/Moscow')).date() + timedelta(days=2)
        db.add(m.Schedule(tenant_id=tenant.id, doctor_id=doctor.id, branch_id=branch.id,
                          weekday=day.weekday(), start_time='09:00', end_time='18:00'))
        patients = [m.Patient(tenant_id=tenant.id, name='CI patient A'), m.Patient(tenant_id=tenant.id, name='CI patient B')]
        db.add_all(patients); db.commit()
        tenant_id, doctor_id, service_id, branch_id = tenant.id, doctor.id, service.id, branch.id
        patient_ids = [p.id for p in patients]
    barrier = Barrier(2)
    def attempt(index):
        with SessionLocal() as db:
            t, p = db.get(m.Tenant, tenant_id), db.get(m.Patient, patient_ids[index])
            barrier.wait(timeout=5)
            try:
                create_appointment(db, t, p, service_id, doctor_id, branch_id,
                    datetime.combine(day, time(10, 0), tzinfo=ZoneInfo('Europe/Moscow')),
                    'concurrent-' + str(index), 'identity-' + str(index))
                db.commit()
                return 201
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [0, 1]))
    assert sorted(outcomes) == [201, 409]
