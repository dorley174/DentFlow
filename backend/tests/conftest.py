import os
from pathlib import Path

os.environ.setdefault('APP_ENV','test')
os.environ.setdefault('ENABLE_DEV_TOOLS','true')
os.environ.setdefault('DATABASE_URL','sqlite:///'+str(Path(__file__).parent.parent/'.test-dentflow.db'))
os.environ.setdefault('ALLOWED_ORIGINS','http://testserver')
os.environ.setdefault('COOKIE_SECURE','false')
os.environ.setdefault('REDIS_URL','')

import pytest
from urllib.parse import urlparse
_test_db_name=urlparse(os.environ['DATABASE_URL']).path.lstrip('/')
if os.environ['APP_ENV']!='test':
    raise RuntimeError('Тесты требуют APP_ENV=test. Разрушительные операции остановлены.')
if not os.environ['DATABASE_URL'].startswith('sqlite') and _test_db_name!='dentflow_test':
    raise RuntimeError('Тесты разрешены только в PostgreSQL dentflow_test. Разрушительные операции остановлены.')
from sqlalchemy import text
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base,engine,SessionLocal
from app.seed import seed_demo

HEADERS={'X-Requested-With':'DentFlow','Origin':'http://testserver'}

@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if engine.dialect.name=='postgresql':
        with engine.begin() as connection:
            connection.execute(text('CREATE EXTENSION IF NOT EXISTS btree_gist'))
            connection.execute(text("""ALTER TABLE appointments ADD CONSTRAINT appointments_no_overlap
            EXCLUDE USING gist (tenant_id WITH =, doctor_id WITH =, tstzrange(start_at,end_at,'[)') WITH &&)
            WHERE (status IN ('scheduled','confirmed','completed'))"""))
    with SessionLocal() as db:
        seed_demo(db)
        db.commit()
    yield

@pytest.fixture
def client():
    with TestClient(app,headers=HEADERS) as client:
        yield client

@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def login(client,role='admin'):
    response=client.post('/api/auth/login',json={'email':role+'@dentflow.local','password':role.title()+'-Demo-2026!'})
    assert response.status_code==200,response.text
    return response.json()['user']


def clinic_and_slot(client,slug='smile-avenue',exclude=None):
    from datetime import timedelta
    from app.db import utcnow
    from zoneinfo import ZoneInfo
    clinic=client.get('/api/public/clinics/'+slug).json()
    service=next(s for s in clinic['services'] if s['name']=='Консультация стоматолога')
    doctor=clinic['doctors'][0]
    day=(utcnow().astimezone(ZoneInfo('Europe/Moscow'))+timedelta(days=1)).date().isoformat()
    response=client.get('/api/public/clinics/'+slug+'/slots',params={'service_id':service['id'],'doctor_id':doctor['id'],'date':day})
    assert response.status_code==200,response.text
    slots=response.json()['slots']
    slot=next(s for s in slots if s['start_at']!=exclude)
    return clinic,service,doctor,slot


def booking_payload(service,doctor,slot,key='test-booking-0001'):
    return {'service_id':service['id'],'doctor_id':doctor['id'],'branch_id':doctor['branch_id'],
            'start_at':slot['start_at'],'patient_name':'Тестовый Гость','phone':'+70000000111',
            'consent_pd':True,'consent_notifications':True,'idempotency_key':key}
