from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .. import models as m, schemas as s
from ..db import get_db, utcnow
from ..config import settings
from ..security import current_user, super_user, hash_password, require_roles
from ..services.common import serial, audit
from ..services.booking import change_appointment
from ..services.chat import request_human_assistance, append_message
from ..services.automations import run_automations
from ..seed import assert_demo_database, reset_demo, seed_plans

router=APIRouter(tags=['Владелец платформы и Dev Stand'])


@router.get('/api/super/overview')
def super_overview(user=Depends(super_user),db:Session=Depends(get_db)):
    tenants=list(db.scalars(select(m.Tenant).order_by(m.Tenant.created_at.desc())))
    plans=list(db.scalars(select(m.Plan).order_by(m.Plan.price_kopecks)))
    plan_prices={p.code:p.price_kopecks for p in plans}
    subscriptions=list(db.scalars(select(m.Subscription)))
    rows=[]
    for tenant in tenants:
        data=serial(tenant)
        data.pop('settings',None)
        subscription=next((x for x in subscriptions if x.tenant_id==tenant.id),None)
        data['subscription']=serial(subscription)
        data['plan_code']=subscription.plan_code if subscription else ''
        data['ai_messages']=db.scalar(select(func.count(m.AIUsage.id)).where(m.AIUsage.tenant_id==tenant.id)) or 0
        rows.append(data)
    integrations=[]
    names={t.id:t.name for t in tenants}
    for integration in db.scalars(select(m.Integration)):
        integrations.append({'id':integration.id,'tenant_id':integration.tenant_id,'tenant_name':names.get(integration.tenant_id,''),
            'name':integration.name,'status':integration.status,'last_error':integration.last_error})
    stats={'total_tenants':len(tenants),'active_tenants':sum(t.status=='active' for t in tenants),
        'ai_messages':db.scalar(select(func.count(m.AIUsage.id))) or 0,
        'appointments':db.scalar(select(func.count(m.Appointment.id))) or 0,
        'pending_notifications':db.scalar(select(func.count(m.Notification.id)).where(m.Notification.status=='pending')) or 0,
        'integration_errors':sum(bool(x['last_error']) for x in integrations),
        'configured_subscription_value_kopecks':sum(plan_prices.get(s.plan_code,0) for s in subscriptions),
        'payment_mode':'DEMO','finance_note':'Цены настроенных тарифов; платежи не принимаются и выручка не подтверждается'}
    return {'tenants':rows,'plans':[serial(p) for p in plans],'stats':stats,'integrations':integrations,
            'connection_requests':[serial(x) for x in db.scalars(select(m.ConnectionRequest).order_by(m.ConnectionRequest.created_at.desc()).limit(500))]}


@router.post('/api/super/tenants',status_code=201)
def create_tenant(data:s.TenantInput,user=Depends(super_user),db:Session=Depends(get_db)):
    if db.scalar(select(m.Tenant.id).where(m.Tenant.slug==data.slug)):
        raise HTTPException(409,'Такой адрес клиники уже занят')
    if db.scalar(select(m.User.id).where(m.User.email==data.owner_email.lower())):
        raise HTTPException(409,'Указанный email уже используется')
    seed_plans(db)
    tenant=m.Tenant(name=data.name,slug=data.slug,phone=data.phone,is_demo=settings.is_demo)
    db.add(tenant);db.flush()
    owner=m.User(tenant_id=tenant.id,name=data.owner_name,email=data.owner_email.lower(),
        password_hash=hash_password(data.owner_password),role='owner')
    db.add(owner)
    db.add(m.AISettings(tenant_id=tenant.id,provider='demo'))
    db.add(m.Subscription(tenant_id=tenant.id,plan_code=data.plan_code,status='demo',payment_mode='DEMO'))
    db.add(m.Integration(tenant_id=tenant.id,name='Встроенное расписание',kind='internal',status='connected',description='PostgreSQL DentFlow'))
    audit(db,tenant.id,user.id,'tenant.created','tenant',tenant.id)
    db.commit()
    return {'tenant':serial(tenant),'message':'Клиника создана. Владелец может войти и добавить филиалы, врачей, услуги и расписание.'}


@router.patch('/api/super/tenants/{item_id}')
def patch_tenant(item_id:str,data:s.SuperTenantPatch,user=Depends(super_user),db:Session=Depends(get_db)):
    tenant=db.get(m.Tenant,item_id)
    if not tenant:
        raise HTTPException(404,'Клиника не найдена')
    values=data.model_dump(exclude_none=True)
    if 'plan_code' in values:
        subscription=db.scalar(select(m.Subscription).where(m.Subscription.tenant_id==tenant.id))
        if not subscription:
            subscription=m.Subscription(tenant_id=tenant.id);db.add(subscription)
        subscription.plan_code=values.pop('plan_code')
    for field,value in values.items():
        setattr(tenant,field,value)
    audit(db,tenant.id,user.id,'tenant.updated','tenant',tenant.id,{'fields':sorted(values)})
    db.commit()
    return {'tenant':serial(tenant)}


@router.patch('/api/super/plans/{code}')
def patch_plan(code:str,data:s.PlanPatch,user=Depends(super_user),db:Session=Depends(get_db)):
    plan=db.scalar(select(m.Plan).where(m.Plan.code==code))
    if not plan:
        raise HTTPException(404,'Тариф не найден')
    for field,value in data.model_dump(exclude_none=True).items():
        setattr(plan,field,value)
    db.commit()
    return {'plan':serial(plan),'message':'Конфигурация тарифа сохранена; денежные средства не списывались'}


def require_dev(user,db):
    if not settings.dev_tools:
        raise HTTPException(404,'Тестовые инструменты недоступны')
    try:
        assert_demo_database()
    except RuntimeError:
        raise HTTPException(403,'Операция запрещена для этой базы данных')
    if user.role=='super_admin':
        tenant=db.scalar(select(m.Tenant).where(m.Tenant.slug=='smile-avenue',m.Tenant.is_demo.is_(True)))
    else:
        require_roles(user,{'owner','manager'})
        tenant=db.scalar(select(m.Tenant).where(m.Tenant.id==user.tenant_id,m.Tenant.is_demo.is_(True)))
    if not tenant:
        raise HTTPException(404,'Демонстрационная клиника не найдена')
    return tenant


@router.post('/api/dev/reset')
def reset(data:s.ResetInput,user=Depends(super_user),db:Session=Depends(get_db)):
    require_dev(user,db)
    tenant=reset_demo(db)
    audit(db,tenant.id,user.id,'demo.reset','tenant',tenant.id)
    db.commit()
    return {'message':'Smile Avenue восстановлена. Войдите в тестовые аккаунты заново. Другие клиники не изменены.',
            'tenant_id':tenant.id}


@router.post('/api/dev/simulate')
def simulate(data:s.SimulateInput,user=Depends(current_user),db:Session=Depends(get_db)):
    tenant=require_dev(user,db)
    result={}
    if data.event=='new_lead':
        patient=m.Patient(tenant_id=tenant.id,name='Симулятор: тестовый пациент',phone='+70000000000')
        db.add(patient);db.flush()
        db.add(m.Lead(tenant_id=tenant.id,patient_id=patient.id,title='Обращение из симулятора',source='demo',stage='Новое обращение'))
    elif data.event in {'cancel','free_slot'}:
        appointment=db.scalar(select(m.Appointment).where(m.Appointment.tenant_id==tenant.id,
            m.Appointment.start_at>utcnow(),m.Appointment.status.in_(['scheduled','confirmed'])).order_by(m.Appointment.start_at))
        if not appointment:
            raise HTTPException(409,'Нет будущих записей для отмены; создайте запись')
        change_appointment(db,tenant,appointment,action='cancel',actor_id=user.id)
    elif data.event=='task':
        db.add(m.Task(tenant_id=tenant.id,title='Задача из симулятора',description='Проверьте работу задач.',due_at=utcnow()))
    elif data.event in {'missed_reply','handoff'}:
        conversation=m.Conversation(tenant_id=tenant.id,channel='web',context={})
        db.add(conversation);db.flush()
        append_message(db,conversation,'patient','Хочу подобрать время для консультации (тест).')
        append_message(db,conversation,'assistant','Подскажите, какой филиал вам удобнее? (тест)')
        if data.event=='handoff':
            request_human_assistance(db,tenant,conversation,'Передача сотруднику из симулятора')
        else:
            conversation.updated_at=utcnow()-timedelta(days=1)
            db.flush()
            result=run_automations(db,tenant.id,utcnow()+timedelta(minutes=data.advance_minutes))
    elif data.event=='reminder':
        next_visit=db.scalar(select(m.Appointment).where(m.Appointment.tenant_id==tenant.id,
            m.Appointment.start_at>utcnow(),m.Appointment.status.in_(['scheduled','confirmed'])).order_by(m.Appointment.start_at))
        if not next_visit:
            raise HTTPException(409,'Создайте будущую запись для проверки напоминания')
        from ..db import aware
        simulated_now=aware(next_visit.start_at)-timedelta(minutes=60)
        result=run_automations(db,tenant.id,simulated_now)
    audit(db,tenant.id,user.id,'demo.simulated','event',details={'event':data.event,'advance_minutes':data.advance_minutes})
    db.commit()
    return {'event':data.event,'message':'Тестовое событие выполнено. Обновите соответствующий раздел кабинета.','result':result}
