from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session
from .. import models as m, schemas as s
from ..db import get_db, utcnow, aware
from ..config import settings
from ..errors import validation_message
from ..security import clinic_user, require_roles, public_user, hash_password, EDIT_ROLES
from ..services.common import serial, items, tenant_item, audit
from ..services.booking import create_appointment, change_appointment, save_consents
from ..services.chat import append_message, payload
from ..services.automations import run_automations

router=APIRouter(prefix='/api/admin',tags=['Кабинет клиники'])

CATALOG_ROLES={'owner','manager'}
RESOURCE_MAP={
 'branches':(m.Branch,s.BranchInput,s.BranchPatch,CATALOG_ROLES),
 'doctors':(m.Doctor,s.DoctorInput,s.DoctorPatch,CATALOG_ROLES),
 'services':(m.Service,s.ServiceInput,s.ServicePatch,CATALOG_ROLES),
 'schedules':(m.Schedule,s.ScheduleInput,s.SchedulePatch,CATALOG_ROLES),
 'leads':(m.Lead,s.LeadInput,s.LeadPatch,EDIT_ROLES),
 'tasks':(m.Task,s.TaskInput,s.TaskPatch,EDIT_ROLES),
 'employees':(m.User,s.EmployeeInput,s.EmployeePatch,{'owner'}),
 'automation_rules':(m.AutomationRule,s.AutomationInput,s.AutomationPatch,CATALOG_ROLES),
}
READ_MAP={k:v[0] for k,v in RESOURCE_MAP.items()}|{'patients':m.Patient,'appointments':m.Appointment,
 'conversations':m.Conversation,'notifications':m.Notification,'integrations':m.Integration,'audit_logs':m.AuditLog}


def visible_items(db,model,user):
    query=select(model).where(model.tenant_id==user.tenant_id)
    if user.role=='doctor':
        if model==m.Appointment:
            query=query.where(m.Appointment.doctor_id==user.doctor_id)
        elif model==m.Patient:
            patient_ids=select(m.Appointment.patient_id).where(m.Appointment.tenant_id==user.tenant_id,m.Appointment.doctor_id==user.doctor_id)
            query=query.where(m.Patient.id.in_(patient_ids))
        elif model==m.Doctor:
            query=query.where(m.Doctor.id==user.doctor_id)
        elif model==m.Schedule:
            query=query.where(m.Schedule.doctor_id==user.doctor_id)
        elif model not in {m.Service,m.Branch}:
            return []
    if model==m.User:
        if user.role not in CATALOG_ROLES:
            return []
        query=query.where(m.User.role.in_(['owner','manager','administrator','doctor']))
    if model==m.AuditLog and user.role not in CATALOG_ROLES:
        return []
    return list(db.scalars(query.order_by(model.created_at.desc()).limit(2000)))


def metrics_for(db,tenant,user):
    appointments=visible_items(db,m.Appointment,user)
    patients=visible_items(db,m.Patient,user)
    leads=visible_items(db,m.Lead,user)
    today=utcnow().astimezone(ZoneInfo(tenant.timezone)).date()
    today_items=[a for a in appointments if aware(a.start_at).astimezone(ZoneInfo(tenant.timezone)).date()==today]
    lead_booked=sum(l.stage in {'Записан','Подтверждён','Посетил','Завершено'} for l in leads)
    ai_messages=db.scalar(select(func.count(m.AIUsage.id)).where(m.AIUsage.tenant_id==tenant.id)) or 0
    return {'appointments_today':len([a for a in today_items if a.status!='cancelled']),
      'active_patients':len([p for p in patients if not p.deleted_at]),
      'new_leads':len([l for l in leads if l.stage in {'Новое обращение','Не обработано'}]),
      'expected_revenue_kopecks':sum(a.price_kopecks for a in appointments if a.status in {'scheduled','confirmed'} and aware(a.start_at)>utcnow()),
      'completed_revenue_kopecks':sum(a.price_kopecks for a in appointments if a.status=='completed'),
      'conversion_rate':round(100*lead_booked/len(leads),1) if leads else 0,
      'ai_messages':ai_messages if user.role!='doctor' else 0,'total_appointments':len(appointments),
      'revenue_note':'Стоимость записей по прайсу, а не подтверждённые кассовые поступления',
      'status_counts':{x:sum(a.status==x for a in appointments) for x in ['scheduled','confirmed','completed','cancelled','no_show']},
      'daily':[{'date':(today+timedelta(days=i)).isoformat(),'appointments':sum(aware(a.start_at).astimezone(ZoneInfo(tenant.timezone)).date()==today+timedelta(days=i) and a.status!='cancelled' for a in appointments)} for i in range(7)]}


@router.get('/bootstrap')
def bootstrap(user=Depends(clinic_user),db:Session=Depends(get_db)):
    tenant=db.get(m.Tenant,user.tenant_id)
    result={'user':public_user(user),'tenant':serial(tenant),'metrics':metrics_for(db,tenant,user)}
    mapping={'branches':m.Branch,'doctors':m.Doctor,'services':m.Service,'patients':m.Patient,'appointments':m.Appointment,
             'leads':m.Lead,'conversations':m.Conversation,'tasks':m.Task,'notifications':m.Notification,
             'automation_rules':m.AutomationRule,'integrations':m.Integration,'staff':m.User,'audit_logs':m.AuditLog,'schedules':m.Schedule}
    for key,model in mapping.items():
        result[key]=[serial(x,db) for x in visible_items(db,model,user)]
    if user.role=='administrator':
        staff=db.scalars(select(m.User).where(m.User.tenant_id==user.tenant_id,m.User.active.is_(True),
            m.User.role.in_(['owner','manager','administrator','doctor'])))
        result['staff']=[{key:getattr(person,key) for key in ['id','name','role','active']} for person in staff]
    ai=db.scalar(select(m.AISettings).where(m.AISettings.tenant_id==user.tenant_id))
    result['ai_settings']=serial(ai) if user.role in CATALOG_ROLES else {'provider':ai.provider if ai else 'demo','enabled':ai.enabled if ai else True}
    subscription=db.scalar(select(m.Subscription).where(m.Subscription.tenant_id==user.tenant_id))
    result['subscription']=serial(subscription) if user.role in CATALOG_ROLES else None
    audit(db,user.tenant_id,user.id,'dashboard.read','tenant',user.tenant_id)
    db.commit()
    return result


@router.get('/settings')
def read_settings(user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,CATALOG_ROLES)
    return {'tenant':serial(db.get(m.Tenant,user.tenant_id)),
            'ai_settings':serial(db.scalar(select(m.AISettings).where(m.AISettings.tenant_id==user.tenant_id)))}


@router.patch('/settings')
def update_settings(data:s.SettingsPatch,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,CATALOG_ROLES)
    tenant=db.get(m.Tenant,user.tenant_id)
    if data.tenant:
        for field,value in data.tenant.model_dump(exclude_none=True).items():
            if field=='logo_url' and value and not (value.startswith('https://') or value.startswith('/')):
                raise HTTPException(422,'Логотип должен иметь HTTPS URL или локальный путь')
            setattr(tenant,field,value)
    ai=db.scalar(select(m.AISettings).where(m.AISettings.tenant_id==user.tenant_id))
    if not ai:
        ai=m.AISettings(tenant_id=user.tenant_id);db.add(ai)
    if data.ai_settings:
        for field,value in data.ai_settings.model_dump(exclude_none=True).items():
            setattr(ai,field,value)
    audit(db,user.tenant_id,user.id,'settings.updated','tenant',user.tenant_id)
    db.commit()
    return {'tenant':serial(tenant),'ai_settings':serial(ai)}


@router.post('/automations/run')
def automations_run(data:s.RunAutomations,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,CATALOG_ROLES)
    if data.advance_minutes and not settings.dev_tools:
        raise HTTPException(403,'Ускорение времени доступно только в Dev Stand')
    result=run_automations(db,user.tenant_id,utcnow()+timedelta(minutes=data.advance_minutes))
    db.commit()
    return result


@router.post('/appointments',status_code=201)
def create_visit(data:s.AdminBookingInput,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,EDIT_ROLES)
    tenant=db.get(m.Tenant,user.tenant_id)
    # Serialize idempotency of staff booking before allocating a new patient.
    db.scalar(select(m.User).where(m.User.id==user.id).with_for_update())
    from hashlib import sha256
    key=sha256(f'{user.id}:{data.idempotency_key}'.encode()).hexdigest()
    existing=db.scalar(select(m.Appointment).where(m.Appointment.tenant_id==tenant.id,m.Appointment.idempotency_key==key))
    if existing:
        patient=tenant_item(db,m.Patient,existing.patient_id,tenant.id)
        same_patient=(data.patient_id==existing.patient_id) if data.patient_id else (data.patient_name==patient.name and data.phone==patient.phone)
        if not same_patient or existing.service_id!=data.service_id or existing.doctor_id!=data.doctor_id or aware(existing.start_at)!=aware(data.start_at):
            raise HTTPException(409,'Этот ключ запроса уже использован для другой записи')
        return {'appointment':serial(existing,db)}
    if data.patient_id:
        patient=tenant_item(db,m.Patient,data.patient_id,tenant.id)
    else:
        patient=m.Patient(tenant_id=tenant.id,name=data.patient_name,phone=data.phone,
            notifications_enabled=data.consent_notifications)
        db.add(patient);db.flush()
        save_consents(db,tenant.id,patient,data.consent_pd,data.consent_notifications,'staff')
    appointment=create_appointment(db,tenant,patient,data.service_id,data.doctor_id,data.branch_id,
        data.start_at,data.idempotency_key,user.id,source='manual',actor_id=user.id)
    db.commit()
    return {'appointment':serial(appointment,db)}


@router.patch('/appointments/{item_id}')
def change_visit(item_id:str,data:s.AppointmentPatch,user=Depends(clinic_user),db:Session=Depends(get_db)):
    appointment=tenant_item(db,m.Appointment,item_id,user.tenant_id)
    if user.role=='doctor':
        if appointment.doctor_id!=user.doctor_id:
            raise HTTPException(404,'Запись не найдена')
        if data.start_at or data.action or data.status not in {'confirmed','completed','no_show'}:
            raise HTTPException(403,'Врач может отметить статус только собственного приёма')
    else:
        require_roles(user,EDIT_ROLES)
    appointment=change_appointment(db,db.get(m.Tenant,user.tenant_id),appointment,
        **data.model_dump(exclude_none=True),actor_id=user.id)
    db.commit()
    return {'appointment':serial(appointment,db)}


@router.get('/conversations/{item_id}/messages')
def read_messages(item_id:str,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,EDIT_ROLES)
    conversation=tenant_item(db,m.Conversation,item_id,user.tenant_id)
    audit(db,user.tenant_id,user.id,'conversation.read','conversation',conversation.id)
    db.commit()
    return payload(db,conversation)


@router.patch('/conversations/{item_id}')
def mode(item_id:str,data:s.ConversationPatch,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,EDIT_ROLES)
    conversation=tenant_item(db,m.Conversation,item_id,user.tenant_id)
    conversation.mode=data.mode
    if data.mode=='ai':
        from ..services.chat import menu
        channel_context={k:v for k,v in (conversation.context or {}).items() if k.startswith('telegram_')}
        conversation.context={**channel_context,'options':menu()}
    audit(db,user.tenant_id,user.id,'conversation.mode_changed','conversation',conversation.id,{'mode':data.mode})
    db.commit()
    return {'item':serial(conversation,db)}


@router.post('/conversations/{item_id}/messages',status_code=201)
def staff_message(item_id:str,data:s.MessageInput,user=Depends(clinic_user),db:Session=Depends(get_db)):
    require_roles(user,EDIT_ROLES)
    conversation=tenant_item(db,m.Conversation,item_id,user.tenant_id)
    if conversation.mode!='human':
        raise HTTPException(409,'Сначала перехватите диалог у AI')
    if conversation.channel=='telegram':
        import re
        if re.search(r'диагноз|медкарт|антибиот|таблет|лекарств|рентген|томограмм|план лечени',data.text.lower()):
            raise HTTPException(422,'В Telegram разрешены только административные сообщения. Медицинские сведения передавайте по утверждённому клиникой защищённому каналу.')
    message=append_message(db,conversation,'staff',data.text)
    if conversation.channel=='telegram' and conversation.external_id:
        db.add(m.Notification(tenant_id=user.tenant_id,patient_id=conversation.patient_id,
            channel='telegram_reply',status='pending',dedup_key='staff:'+message.id,
            title='Ответ администратора',text=data.text))
    audit(db,user.tenant_id,user.id,'conversation.staff_replied','conversation',conversation.id)
    db.commit()
    return {'message':serial(message),'messages':payload(db,conversation)['messages']}


def validate_references(db,user,resource,data,item=None):
    for field,model in [('branch_id',m.Branch),('doctor_id',m.Doctor),('patient_id',m.Patient),('assigned_to',m.User)]:
        if data.get(field):
            referenced=tenant_item(db,model,data[field],user.tenant_id)
            if field=='assigned_to' and (not referenced.active or referenced.role not in {'owner','manager','administrator','doctor'}):
                raise HTTPException(422,'Ответственным может быть только активный сотрудник клиники')
    if resource=='employees':
        role=data.get('role',item.role if item else None)
        doctor_id=data.get('doctor_id',item.doctor_id if item else None)
        if role=='doctor' and not doctor_id:
            raise HTTPException(422,'Для врача укажите doctor_id из справочника')
        if item and item.role=='owner':
            raise HTTPException(403,'Владельца нельзя изменить через управление сотрудниками')
    if resource=='schedules':
        source={k:getattr(item,k) for k in s.ScheduleInput.model_fields} if item else {}
        source.update(data)
        try:
            checked=s.ScheduleInput.model_validate(source)
        except ValidationError as exc:
            raise HTTPException(422,'; '.join(validation_message(e) for e in exc.errors()))
        doctor=tenant_item(db,m.Doctor,checked.doctor_id,user.tenant_id)
        db.scalar(select(m.Doctor).where(m.Doctor.id==doctor.id,m.Doctor.tenant_id==user.tenant_id).with_for_update())
        if item and item.doctor_id!=doctor.id:
            raise HTTPException(422,'Измените часы существующего врача или создайте отдельное расписание другого врача')
        if doctor.branch_id!=checked.branch_id:
            raise HTTPException(422,'Филиал расписания должен совпадать с филиалом врача')
        tenant=db.get(m.Tenant,user.tenant_id)
        upcoming=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==user.tenant_id,
            m.Appointment.doctor_id==doctor.id,m.Appointment.status.in_(['scheduled','confirmed']),m.Appointment.start_at>utcnow())))
        for appointment in upcoming:
            start=aware(appointment.start_at).astimezone(ZoneInfo(tenant.timezone))
            end=aware(appointment.end_at).astimezone(ZoneInfo(tenant.timezone))
            relevant={checked.weekday}
            if item:
                relevant.add(item.weekday)
            if start.weekday() not in relevant:
                continue
            st,en=start.strftime('%H:%M'),end.strftime('%H:%M')
            valid=(checked.active and start.weekday()==checked.weekday and checked.start_time<=st and en<=checked.end_time)
            if checked.break_start and st<checked.break_end and en>checked.break_start:
                valid=False
            if not valid:
                raise HTTPException(409,'В этом расписании уже есть будущие визиты. Сначала перенесите или отмените их.')
    if resource=='doctors' and 'service_ids' in data:
        for service_id in data['service_ids'] or []:
            tenant_item(db,m.Service,service_id,user.tenant_id)


def parse(schema,raw):
    try:
        return schema.model_validate(raw).model_dump(exclude_unset=True)
    except ValidationError as exc:
        raise HTTPException(422,{'message':'Проверьте заполненные поля','errors':[
            {'field':'.'.join(str(x) for x in e['loc']),'message':validation_message(e)} for e in exc.errors()]})


def save_doctor_services(db,user,doctor,service_ids):
    db.execute(delete(m.DoctorService).where(m.DoctorService.tenant_id==user.tenant_id,m.DoctorService.doctor_id==doctor.id))
    for service_id in set(service_ids or []):
        db.add(m.DoctorService(tenant_id=user.tenant_id,doctor_id=doctor.id,service_id=service_id))


@router.get('/{resource}')
def list_resource(resource:str,user=Depends(clinic_user),db:Session=Depends(get_db)):
    model=READ_MAP.get(resource)
    if not model:
        raise HTTPException(404,'Раздел не найден')
    records=[serial(x,db) for x in visible_items(db,model,user)]
    if model in {m.Patient,m.Appointment}:
        audit(db,user.tenant_id,user.id,'records.read',resource,details={'count':len(records)})
        db.commit()
    return {'items':records,resource:records}


@router.post('/{resource}',status_code=201)
def create_resource(resource:str,raw:dict,user=Depends(clinic_user),db:Session=Depends(get_db)):
    config=RESOURCE_MAP.get(resource)
    if not config:
        raise HTTPException(404,'Создание в этом разделе недоступно')
    model,schema,_,roles=config
    require_roles(user,roles)
    data=parse(schema,raw)
    validate_references(db,user,resource,data)
    if resource=='branches':
        db.scalar(select(m.Tenant).where(m.Tenant.id==user.tenant_id).with_for_update())
        subscription=db.scalar(select(m.Subscription).where(m.Subscription.tenant_id==user.tenant_id))
        plan=db.scalar(select(m.Plan).where(m.Plan.code==subscription.plan_code)) if subscription else None
        count=db.scalar(select(func.count(m.Branch.id)).where(m.Branch.tenant_id==user.tenant_id,m.Branch.active.is_(True))) or 0
        if plan and count>=plan.branch_limit:
            raise HTTPException(403,'Достигнут лимит активных филиалов вашего тарифа')
    service_ids=data.pop('service_ids',None)
    if resource=='employees':
        data['email']=data['email'].lower()
        data['password_hash']=hash_password(data.pop('password'))
    item=model(tenant_id=user.tenant_id,**data)
    db.add(item);db.flush()
    if resource=='doctors' and service_ids is not None:
        save_doctor_services(db,user,item,service_ids)
    audit(db,user.tenant_id,user.id,resource+'.created',resource,item.id)
    db.commit()
    return {'item':serial(item,db)}


@router.patch('/{resource}/{item_id}')
def patch_resource(resource:str,item_id:str,raw:dict,user=Depends(clinic_user),db:Session=Depends(get_db)):
    config=RESOURCE_MAP.get(resource)
    if not config:
        raise HTTPException(404,'Изменение в этом разделе недоступно')
    model,_,schema,roles=config
    require_roles(user,roles)
    item=tenant_item(db,model,item_id,user.tenant_id)
    if resource=='doctors':
        db.scalar(select(m.Doctor).where(m.Doctor.id==item.id,m.Doctor.tenant_id==user.tenant_id).with_for_update())
    data=parse(schema,raw)
    validate_references(db,user,resource,data,item)
    if resource=='branches' and data.get('active') is True and not item.active:
        db.scalar(select(m.Tenant).where(m.Tenant.id==user.tenant_id).with_for_update())
        subscription=db.scalar(select(m.Subscription).where(m.Subscription.tenant_id==user.tenant_id))
        plan=db.scalar(select(m.Plan).where(m.Plan.code==subscription.plan_code)) if subscription else None
        count=db.scalar(select(func.count(m.Branch.id)).where(m.Branch.tenant_id==user.tenant_id,m.Branch.active.is_(True))) or 0
        if plan and count>=plan.branch_limit:
            raise HTTPException(403,'Достигнут лимит активных филиалов вашего тарифа')
    if resource=='doctors' and 'branch_id' in data and data['branch_id']!=item.branch_id:
        future=db.scalar(select(m.Appointment.id).where(m.Appointment.tenant_id==user.tenant_id,
            m.Appointment.doctor_id==item.id,m.Appointment.status.in_(['scheduled','confirmed']),m.Appointment.start_at>utcnow()))
        if future:
            raise HTTPException(409,'Сначала перенесите будущие визиты врача перед сменой филиала')
    service_ids=data.pop('service_ids',None)
    if resource=='employees':
        if data.get('email'):
            data['email']=data['email'].lower()
        if data.get('password'):
            data['password_hash']=hash_password(data.pop('password'))
        elif 'password' in data:
            data.pop('password')
    # Explicit Pydantic whitelist above prevents tenant/role escalation and mass assignment.
    nullable={'assigned_to','patient_id','due_at','break_start','break_end','doctor_id'}
    for field,value in data.items():
        if value is None and field not in nullable:
            raise HTTPException(422,'Поле '+field+' не может быть пустым')
        setattr(item,field,value)
    if resource=='doctors' and service_ids is not None:
        save_doctor_services(db,user,item,service_ids)
    if resource=='employees' and ('password_hash' in data or 'active' in data or 'role' in data):
        db.execute(delete(m.AuthSession).where(m.AuthSession.user_id==item.id))
    audit(db,user.tenant_id,user.id,resource+'.updated',resource,item.id,{'fields':sorted(data.keys())})
    db.commit()
    return {'item':serial(item,db)}
