from datetime import date as Date
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db, utcnow
from .. import models as m, schemas as s
from ..security import visitor_session, optional_user
from ..services.common import tenant_by_slug, serial, tenant_item, audit
from ..services.booking import available_slots, identity_patient, save_consents, create_appointment, change_appointment
from ..services.chat import get_or_create_conversation, handle_message, payload
from ..config import settings

router=APIRouter(prefix='/api/public',tags=['Пациент и публичный сайт'])


@router.get('/config')
def config(db:Session=Depends(get_db)):
    plans=list(db.scalars(select(m.Plan).order_by(m.Plan.price_kopecks)))
    return {'environment':settings.app_env,'dev_tools':settings.dev_tools,
            'plans':[serial(p) for p in plans],'prices_are_proposals':True,
            'ai_default':'demo','payment_mode':'DEMO'}


@router.post('/leads',status_code=201)
def connection_request(data:s.ConnectionInput,db:Session=Depends(get_db)):
    item=m.ConnectionRequest(**data.model_dump())
    db.add(item);db.commit()
    return {'id':item.id,'message':'Заявка сохранена для владельца платформы. Сообщения во внешние сервисы не отправлялись.'}


@router.get('/clinics/{slug}')
def clinic(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant=tenant_by_slug(db,slug)
    visitor_session(request,response,db)
    db.commit()
    public_tenant={k:getattr(tenant,k) for k in ['id','name','slug','phone','description','brand_color','logo_url','timezone','is_demo']}
    return {'tenant':public_tenant,
        'branches':[serial(x) for x in db.scalars(select(m.Branch).where(m.Branch.tenant_id==tenant.id,m.Branch.active.is_(True)))],
        'doctors':[serial(x,db) for x in db.scalars(select(m.Doctor).where(m.Doctor.tenant_id==tenant.id,m.Doctor.active.is_(True)))],
        'services':[serial(x) for x in db.scalars(select(m.Service).where(m.Service.tenant_id==tenant.id,m.Service.active.is_(True)))]}


@router.get('/clinics/{slug}/slots')
def slots(slug:str,service_id:str,date:Date,doctor_id:str|None=None,branch_id:str|None=None,db:Session=Depends(get_db)):
    tenant=tenant_by_slug(db,slug)
    return {'slots':available_slots(db,tenant,service_id,date,doctor_id,branch_id)}


def patient_context(slug,request,response,db,create=False,data=None):
    tenant=tenant_by_slug(db,slug)
    visitor=visitor_session(request,response,db)
    user=optional_user(request,db)
    patient=identity_patient(db,tenant,visitor,user,
        name=data.patient_name if data else None,phone=data.phone if data else None,
        notifications=data.consent_notifications if data else False,create=create)
    return tenant,visitor,user,patient


@router.post('/clinics/{slug}/appointments',status_code=201)
def book(slug:str,data:s.BookingInput,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db,True,data)
    save_consents(db,tenant.id,patient,data.consent_pd,data.consent_notifications)
    conversation=db.scalar(select(m.Conversation).where(m.Conversation.tenant_id==tenant.id,
        m.Conversation.session_id==visitor.id,m.Conversation.channel=='web'))
    appointment=create_appointment(db,tenant,patient,data.service_id,data.doctor_id,data.branch_id,
        data.start_at,data.idempotency_key,visitor.id,conversation_id=conversation.id if conversation else None)
    if conversation:
        conversation.patient_id=patient.id
    db.commit()
    return {'appointment':serial(appointment,db),'patient':serial(patient)}


@router.get('/clinics/{slug}/my-appointments')
def my_appointments(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    appointments=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==tenant.id,
        m.Appointment.patient_id==patient.id).order_by(m.Appointment.start_at.desc()))) if patient else []
    db.commit()
    return {'appointments':[serial(x,db) for x in appointments]}


@router.patch('/clinics/{slug}/appointments/{item_id}')
def modify_appointment(slug:str,item_id:str,data:s.AppointmentPatch,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    appointment=tenant_item(db,m.Appointment,item_id,tenant.id)
    if not patient or appointment.patient_id!=patient.id:
        raise HTTPException(404,'Запись не найдена')
    if data.status not in {None,'cancelled','confirmed'} or (data.action is None and data.start_at is None and data.status is None):
        raise HTTPException(403,'Пациент может подтвердить, перенести или отменить свой визит')
    appointment=change_appointment(db,tenant,appointment,**data.model_dump(exclude_none=True))
    db.commit()
    return {'appointment':serial(appointment,db)}


@router.get('/clinics/{slug}/chat')
def chat_history(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    conversation=get_or_create_conversation(db,tenant,visitor,patient)
    db.commit()
    return payload(db,conversation)


@router.post('/clinics/{slug}/chat')
def chat(slug:str,data:s.ChatInput,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    conversation=get_or_create_conversation(db,tenant,visitor,patient)
    # Commit only identity/welcome initialization before optional external classification.
    # Booking itself remains a single transaction inside the engine.
    db.commit()
    result=handle_message(db,tenant,conversation,data.message,data.action,data.data,visitor,user)
    db.commit()
    return result


@router.get('/clinics/{slug}/notifications')
def notifications(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    records=list(db.scalars(select(m.Notification).where(m.Notification.tenant_id==tenant.id,
        m.Notification.patient_id==patient.id).order_by(m.Notification.created_at.desc()).limit(100))) if patient else []
    db.commit()
    return {'notifications':[serial(x) for x in records]}


@router.get('/clinics/{slug}/consents')
def consents(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    db.commit()
    return {'notifications_enabled':patient.notifications_enabled if patient else False,
            'marketing_enabled':patient.marketing_enabled if patient else False,
            'version':'2026-11-05'}


@router.patch('/clinics/{slug}/consents')
def update_consents(slug:str,data:s.ConsentInput,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    if not patient:
        raise HTTPException(404,'Профиль пациента ещё не создан')
    for field,value in data.model_dump(exclude_none=True).items():
        setattr(patient,field,value)
        db.add(m.ConsentRecord(tenant_id=tenant.id,patient_id=patient.id,
            purpose='notifications' if field=='notifications_enabled' else 'marketing',granted=value))
    if not patient.notifications_enabled:
        for notification in db.scalars(select(m.Notification).where(m.Notification.tenant_id==tenant.id,
            m.Notification.patient_id==patient.id,m.Notification.status=='pending')):
            notification.status='cancelled'
    if not patient.marketing_enabled:
        for notification in db.scalars(select(m.Notification).where(m.Notification.tenant_id==tenant.id,
            m.Notification.patient_id==patient.id,m.Notification.status=='pending',
            m.Notification.dedup_key.like('reactivation:%'))):
            notification.status='cancelled'
    audit(db,tenant.id,None,'consent.updated','patient',patient.id)
    db.commit()
    return {'notifications_enabled':patient.notifications_enabled,'marketing_enabled':patient.marketing_enabled}


@router.get('/clinics/{slug}/my-data')
def export_data(slug:str,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    if not patient:
        raise HTTPException(404,'Профиль пациента не найден')
    conversations=list(db.scalars(select(m.Conversation).where(m.Conversation.tenant_id==tenant.id,m.Conversation.patient_id==patient.id)))
    result={'patient':serial(patient),'appointments':[serial(x,db) for x in db.scalars(select(m.Appointment).where(
        m.Appointment.tenant_id==tenant.id,m.Appointment.patient_id==patient.id))],
        'consents':[serial(x) for x in db.scalars(select(m.ConsentRecord).where(m.ConsentRecord.tenant_id==tenant.id,m.ConsentRecord.patient_id==patient.id))],
        'conversations':[payload(db,c) for c in conversations]}
    audit(db,tenant.id,None,'patient.exported','patient',patient.id)
    db.commit()
    return result


@router.post('/clinics/{slug}/delete-my-data')
def request_delete(slug:str,data:s.DeletePatientInput,request:Request,response:Response,db:Session=Depends(get_db)):
    tenant,visitor,user,patient=patient_context(slug,request,response,db)
    if not patient:
        raise HTTPException(404,'Профиль пациента не найден')
    # Deletion must respect contract/legal retention. Create an auditable operator request;
    # never claim all medical/business records were erased automatically.
    key=f'erasure:{patient.id}'
    if not db.scalar(select(m.Task.id).where(m.Task.tenant_id==tenant.id,m.Task.dedup_key==key)):
        db.add(m.Task(tenant_id=tenant.id,patient_id=patient.id,title='Запрос на удаление персональных данных',
            description='Проверить личность, правовое основание и сроки хранения. Ответить пациенту и оформить удаление допустимых данных.',
            dedup_key=key,due_at=utcnow()))
    patient.notifications_enabled=False
    patient.marketing_enabled=False
    audit(db,tenant.id,None,'patient.erasure_requested','patient',patient.id)
    db.commit()
    return {'status':'requested','message':'Запрос на удаление передан клинике. Рассылки отключены. Сотрудник проверит сроки обязательного хранения и сообщит результат.'}
