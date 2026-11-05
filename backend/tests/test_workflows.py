from datetime import datetime,timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app import models as m
from app.db import utcnow,aware
from app.config import settings
from .conftest import login,clinic_and_slot,booking_payload,HEADERS


def test_booking_admin_reschedule_conflict_and_reuse(client,db):
    clinic,service,doctor,slot=clinic_and_slot(client)
    url='/api/public/clinics/smile-avenue'
    body=booking_payload(service,doctor,slot)
    created=client.post(url+'/appointments',json=body)
    assert created.status_code==201,created.text
    appointment=created.json()['appointment']
    repeat=client.post(url+'/appointments',json=body)
    assert repeat.status_code==201 and repeat.json()['appointment']['id']==appointment['id']
    assert len(client.get(url+'/my-appointments').json()['appointments'])==1
    patient_id=appointment['patient_id']
    assert db.scalar(select(func.count(m.Lead.id)).where(m.Lead.patient_id==patient_id))==1
    assert db.scalar(select(func.count(m.Patient.id)).where(m.Patient.id==patient_id))==1
    assert client.get(url+'/notifications').json()['notifications'][0]['title']=='Запись создана'
    with TestClient(app,headers=HEADERS) as stranger:
        stranger.get(url)
        conflict=stranger.post(url+'/appointments',json=booking_payload(service,doctor,slot,'another-key-1111'))
        assert conflict.status_code==409,conflict.text
        assert stranger.patch(url+'/appointments/'+appointment['id'],json={'action':'cancel'}).status_code==404
    login(client)
    admin=client.get('/api/admin/bootstrap').json()
    assert any(a['id']==appointment['id'] for a in admin['appointments'])
    free=client.get(url+'/slots',params={'service_id':service['id'],'doctor_id':doctor['id'],'date':slot['start_at'][:10]}).json()['slots']
    later=next(s for s in free if datetime.fromisoformat(s['start_at'])>=datetime.fromisoformat(slot['end_at']))
    moved=client.patch('/api/admin/appointments/'+appointment['id'],json={'action':'reschedule','start_at':later['start_at']})
    assert moved.status_code==200,moved.text
    slots=client.get(url+'/slots',params={'service_id':service['id'],'doctor_id':doctor['id'],'date':slot['start_at'][:10]}).json()['slots']
    assert any(s['start_at']==slot['start_at'] for s in slots)
    with TestClient(app,headers=HEADERS) as another:
        another.get(url)
        new_booking=another.post(url+'/appointments',json=booking_payload(service,doctor,slot,'new-patient-1111'))
        assert new_booking.status_code==201
        assert new_booking.json()['appointment']['patient_id']!=patient_id  # same unverified phone is not an identity
    assert len(client.get(url+'/my-appointments').json()['appointments'])==1


def test_tenant_and_role_isolation(client,db):
    first=client.get('/api/public/clinics/smile-avenue').json()
    other,service,doctor,slot=clinic_and_slot(client,'aurora-dental')
    login(client,'admin')
    assert client.patch('/api/admin/services/'+service['id'],json={'price_kopecks':1}).status_code==403
    other_appointment=db.scalar(select(m.Appointment).where(m.Appointment.tenant_id==other['tenant']['id']))
    assert client.patch('/api/admin/appointments/'+other_appointment.id,json={'action':'cancel'}).status_code==404
    assert client.patch('/api/admin/settings',json={'tenant':{'name':'Hack'}}).status_code==403
    login(client,'owner')
    assert client.patch('/api/admin/services/'+service['id'],json={'price_kopecks':1}).status_code==404
    assert client.post('/api/admin/doctors',json={'name':'Тест','branch_id':other['branches'][0]['id'],'service_ids':[]}).status_code==404
    assert client.post('/api/admin/employees',json={'name':'Тест','email':'x@example.org','password':'Long-password-2026!','role':'super_admin'}).status_code==422
    login(client,'patient')
    assert client.get('/api/admin/bootstrap').status_code==403
    assert client.get('/api/super/overview').status_code==403
    login(client,'super')
    assert client.get('/api/admin/bootstrap').status_code==403
    overview=client.get('/api/super/overview').json()
    assert 'patients' not in overview and 'conversations' not in overview


def test_doctor_only_own_schedule(client,db):
    user=login(client,'doctor')
    data=client.get('/api/admin/bootstrap').json()
    assert data['appointments'] and all(a['doctor_id']==user['doctor_id'] for a in data['appointments'])
    assert data['conversations']==[] and data['leads']==[] and data['staff']==[]
    other=db.scalar(select(m.Appointment).where(m.Appointment.doctor_id!=user['doctor_id'],m.Appointment.tenant_id==user['tenant_id']))
    assert client.patch('/api/admin/appointments/'+other.id,json={'status':'completed'}).status_code==404
    own=data['appointments'][0]
    assert client.patch('/api/admin/appointments/'+own['id'],json={'status':'confirmed'}).status_code==200
    assert client.post('/api/admin/tasks',json={'title':'Не разрешено'}).status_code==403


def test_guided_chat_books_and_handoff(client,db):
    base='/api/public/clinics/smile-avenue'
    client.get(base)
    result=client.get(base+'/chat')
    assert result.status_code==200,result.text
    conversation_id=result.json()['conversation']['id']
    for action in ['book','select_service','select_branch','select_doctor','select_slot']:
        if action=='book':
            body={'message':'Записаться','action':'book'}
        else:
            option=next(o for o in result.json()['options'] if o['action']==action)
            body={'message':option['label'],'action':option['action'],'data':option['data']}
        result=client.post(base+'/chat',json=body)
        assert result.status_code==200,result.text
    result=client.post(base+'/chat',json={'message':'Тестовый Гость, +7 000 000-01-11'})
    assert result.status_code==200,result.text
    consent=next(o for o in result.json()['options'] if o['action']=='confirm_booking')
    result=client.post(base+'/chat',json={'message':consent['label'],'action':consent['action'],'data':consent['data']})
    assert result.status_code==200,result.text
    assert 'Запись подтверждена' in result.json()['messages'][-1]['text']
    assert len(client.get(base+'/my-appointments').json()['appointments'])==1
    assert db.scalar(select(func.count(m.Lead.id)).where(m.Lead.conversation_id==conversation_id))==1
    result=client.post(base+'/chat',json={'message':'Позвать администратора','action':'human'})
    assert result.json()['conversation']['mode']=='human'
    login(client,'admin')
    reply=client.post('/api/admin/conversations/'+conversation_id+'/messages',json={'text':'Здравствуйте! Я подключилась к диалогу.'})
    assert reply.status_code==201,reply.text
    history=client.get(base+'/chat').json()
    assert history['messages'][-1]['role']=='staff'


def test_medical_question_handoffs_without_diagnosis(client):
    base='/api/public/clinics/smile-avenue'
    client.get(base)
    response=client.post(base+'/chat',json={'message':'Болит зуб, какой антибиотик принимать?'})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['conversation']['mode']=='human'
    assert 'специалист' in data['messages'][-1]['text']


def test_staff_booking_idempotency(client):
    clinic,service,doctor,slot=clinic_and_slot(client)
    login(client)
    data=booking_payload(service,doctor,slot,'manual-booking-key')
    first=client.post('/api/admin/appointments',json=data)
    second=client.post('/api/admin/appointments',json=data)
    assert first.status_code==201,first.text
    assert second.status_code==201,second.text
    assert first.json()['appointment']['id']==second.json()['appointment']['id']


def test_reset_protection_and_second_tenant_preserved(client,db,monkeypatch):
    second=db.scalar(select(m.Tenant).where(m.Tenant.slug=='aurora-dental')).id
    login(client,'owner')
    assert client.post('/api/dev/reset',json={'confirmation':'RESET SMILE AVENUE'}).status_code==403
    login(client,'super')
    assert client.post('/api/dev/reset',json={'confirmation':'bad'}).status_code==422
    monkeypatch.setattr(settings,'enable_dev_tools',False)
    assert client.post('/api/dev/reset',json={'confirmation':'RESET SMILE AVENUE'}).status_code==404
    monkeypatch.setattr(settings,'enable_dev_tools',True)
    response=client.post('/api/dev/reset',json={'confirmation':'RESET SMILE AVENUE'})
    assert response.status_code==200,response.text
    db.expire_all()
    assert db.get(m.Tenant,second)
    smile=db.scalar(select(m.Tenant).where(m.Tenant.slug=='smile-avenue'))
    assert db.scalar(select(func.count(m.Patient.id)).where(m.Patient.tenant_id==smile.id))==30


def test_consents_export_and_deletion_request(client):
    clinic,service,doctor,slot=clinic_and_slot(client)
    base='/api/public/clinics/smile-avenue'
    assert client.post(base+'/appointments',json=booking_payload(service,doctor,slot)).status_code==201
    data=client.get(base+'/my-data').json()
    assert data['patient']['name']=='Тестовый Гость'
    assert len(data['appointments'])==1
    response=client.patch(base+'/consents',json={'notifications_enabled':False,'marketing_enabled':False})
    assert response.status_code==200 and not response.json()['notifications_enabled']
    response=client.post(base+'/delete-my-data',json={'confirmation':'DELETE MY DATA'})
    assert response.status_code==200 and response.json()['status']=='requested'
    login(client)
    assert any('удаление' in x['title'] for x in client.get('/api/admin/tasks').json()['items'])


def test_automations_dedup_and_optout(client,db):
    from app.services.automations import run_automations
    clinic,service,doctor,slot=clinic_and_slot(client)
    base='/api/public/clinics/smile-avenue'
    created=client.post(base+'/appointments',json=booking_payload(service,doctor,slot)).json()['appointment']
    tenant_id=clinic['tenant']['id']
    now=datetime.fromisoformat(created['start_at'])-timedelta(minutes=60)
    first=run_automations(db,tenant_id,now)
    db.commit()
    second=run_automations(db,tenant_id,now)
    db.commit()
    assert first['notifications_created']>0
    assert second['notifications_created']==0 and second['tasks_created']==0
    client.patch(base+'/consents',json={'notifications_enabled':False})
    patient=db.get(m.Patient,created['patient_id']);db.refresh(patient)
    assert not patient.notifications_enabled


def test_csrf_timezone_extra_fields_and_inactive_tenant(client):
    with TestClient(app) as unsafe:
        assert unsafe.post('/api/auth/login',json={'email':'admin@dentflow.local','password':'Admin-Demo-2026!'}).status_code==403
    bad=client.post('/api/auth/login',json={'email':'admin@dentflow.local','password':'Admin-Demo-2026!'},headers={'Origin':'https://evil.example'})
    assert bad.status_code==403
    clinic,service,doctor,slot=clinic_and_slot(client)
    data=booking_payload(service,doctor,slot)
    data['start_at']=datetime.fromisoformat(slot['start_at']).replace(tzinfo=None).isoformat()
    assert client.post('/api/public/clinics/smile-avenue/appointments',json=data).status_code==422
    data=booking_payload(service,doctor,slot);data['tenant_id']='evil'
    assert client.post('/api/public/clinics/smile-avenue/appointments',json=data).status_code==422
    login(client,'super')
    assert client.patch('/api/super/tenants/'+clinic['tenant']['id'],json={'status':'blocked'}).status_code==200
    assert client.get('/api/public/clinics/smile-avenue').status_code==404
    assert client.post('/api/auth/login',json={'email':'admin@dentflow.local','password':'Admin-Demo-2026!'}).status_code==401


def test_catalog_schedule_and_super_creation(client):
    login(client,'super')
    created=client.post('/api/super/tenants',json={'name':'Новая клиника','slug':'new-clinic','owner_name':'Новый Владелец',
        'owner_email':'owner@new.example','owner_password':'Secure-owner-2026!','plan_code':'START'})
    assert created.status_code==201,created.text
    assert client.post('/api/auth/login',json={'email':'owner@new.example','password':'Secure-owner-2026!'}).status_code==200
    branch=client.post('/api/admin/branches',json={'name':'Главный','address':'Тестовый адрес'}).json()['item']
    service=client.post('/api/admin/services',json={'name':'Осмотр','duration_minutes':30,'price_kopecks':150000}).json()['item']
    doctor=client.post('/api/admin/doctors',json={'name':'Доктор Тест','branch_id':branch['id'],'service_ids':[service['id']]}).json()['item']
    from zoneinfo import ZoneInfo
    tomorrow=(utcnow().astimezone(ZoneInfo('Europe/Moscow'))+timedelta(days=1)).date()
    response=client.post('/api/admin/schedules',json={'doctor_id':doctor['id'],'branch_id':branch['id'],'weekday':tomorrow.weekday(),
        'start_time':'09:00','end_time':'18:00','break_start':'13:00','break_end':'14:00'})
    assert response.status_code==201,response.text
    slots=client.get('/api/public/clinics/new-clinic/slots',params={'service_id':service['id'],'doctor_id':doctor['id'],'date':tomorrow.isoformat()}).json()['slots']
    assert slots and all(not x['start_at'][11:16].startswith('13:') for x in slots)


def test_overlapping_intervals_and_schedule_edits(client):
    clinic,service,doctor,slot=clinic_and_slot(client)
    base='/api/public/clinics/smile-avenue'
    created=client.post(base+'/appointments',json=booking_payload(service,doctor,slot))
    assert created.status_code==201
    overlapping={**slot,'start_at':(datetime.fromisoformat(slot['start_at'])+timedelta(minutes=15)).isoformat()}
    response=client.post(base+'/appointments',json=booking_payload(service,doctor,overlapping,'overlap-key-1111'))
    assert response.status_code==409
    login(client,'owner')
    schedules=client.get('/api/admin/schedules').json()['items']
    weekday=datetime.fromisoformat(slot['start_at']).weekday()
    schedule=next(s for s in schedules if s['doctor_id']==doctor['id'] and s['weekday']==weekday)
    assert client.patch('/api/admin/schedules/'+schedule['id'],json={'active':False}).status_code==409
    assert client.patch('/api/admin/schedules/'+schedule['id'],json={'start_time':'20:00'}).status_code==422


def test_missing_consent_and_account_session_separation(client):
    clinic,service,doctor,slot=clinic_and_slot(client)
    base='/api/public/clinics/smile-avenue'
    body=booking_payload(service,doctor,slot)
    assert client.post(base+'/appointments',json={**body,'consent_pd':False}).status_code==422
    assert client.get(base+'/my-appointments').json()['appointments']==[]
    assert client.post(base+'/appointments',json=body).status_code==201
    login(client,'patient')
    assert client.get(base+'/my-appointments').json()['appointments']==[]
    assert client.post('/api/auth/logout',json={}).status_code==200
    assert client.get(base+'/my-appointments').json()['appointments']==[]


def test_production_settings_reject_demo_and_insecure_defaults():
    from app.config import Settings
    from pydantic import ValidationError
    import pytest
    with pytest.raises(ValidationError):
        Settings(app_env='production',database_url='postgresql+psycopg://u:p@localhost/dentflow_prod',
            cookie_secure=False,enable_dev_tools=True,secret_key='short',redis_url='redis://localhost')
    with pytest.raises(ValidationError):
        Settings(app_env='production',database_url='postgresql+psycopg://u:p@localhost/dentflow_devstand',
            cookie_secure=True,enable_dev_tools=False,secret_key='0123456789abcdef'*4,
            allowed_origins='https://app.example.ru',redis_url='redis://localhost')


def test_marketing_optout_cancels_queued_reactivation_only(client,db):
    clinic,service,doctor,slot=clinic_and_slot(client)
    base='/api/public/clinics/smile-avenue'
    created=client.post(base+'/appointments',json=booking_payload(service,doctor,slot)).json()['appointment']
    patient_id=created['patient_id'];tenant_id=clinic['tenant']['id']
    client.patch(base+'/consents',json={'marketing_enabled':True,'notifications_enabled':True})
    campaign=m.Notification(tenant_id=tenant_id,patient_id=patient_id,title='Возвращайтесь',channel='telegram',
        status='pending',dedup_key='reactivation:test:'+patient_id)
    reminder=m.Notification(tenant_id=tenant_id,patient_id=patient_id,title='Напоминание',channel='telegram',
        status='pending',dedup_key='reminder:test:'+patient_id)
    db.add_all([campaign,reminder]);db.commit()
    response=client.patch(base+'/consents',json={'marketing_enabled':False})
    assert response.status_code==200 and response.json()['notifications_enabled'] is True
    db.refresh(campaign);db.refresh(reminder)
    assert campaign.status=='cancelled' and reminder.status=='pending'
