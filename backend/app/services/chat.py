"""Shared administrative engine for web chat and Telegram.

The default demo engine is deterministic, uses actual database tools and does not
send patient text to any LLM. Booking is a guided, consent-based transaction.
"""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, func
from .. import models as m
from ..db import utcnow, aware, uid
from ..schemas import validate_phone
from .common import tenant_item, serial, audit
from .booking import available_slots, create_appointment, change_appointment, identity_patient, save_consents


def option(label, action, **data):
    return {'label':label,'action':action,'data':data}


def menu():
    return [option('Записаться на приём','book'),option('Услуги и цены','services'),
            option('Наши врачи','doctors'),option('Мои записи','appointments'),
            option('Позвать администратора','human')]


def append_message(db, conversation, role, text):
    message = m.Message(tenant_id=conversation.tenant_id, conversation_id=conversation.id, role=role, text=text)
    db.add(message)
    conversation.updated_at = utcnow()
    db.flush()
    return message


def get_or_create_conversation(db, tenant, visitor=None, patient=None, channel='web', external_id=None):
    query = select(m.Conversation).where(m.Conversation.tenant_id == tenant.id, m.Conversation.channel == channel)
    if external_id is not None:
        query = query.where(m.Conversation.external_id == str(external_id))
    elif visitor:
        query = query.where(m.Conversation.session_id == visitor.id)
    else:
        raise HTTPException(401, 'Не удалось определить сессию диалога')
    conversation = db.scalar(query)
    if not conversation:
        ai = db.scalar(select(m.AISettings).where(m.AISettings.tenant_id == tenant.id))
        conversation = m.Conversation(tenant_id=tenant.id, session_id=visitor.id if visitor else None,
            patient_id=patient.id if patient else None, channel=channel,
            external_id=str(external_id) if external_id is not None else None, context={'options':menu()})
        db.add(conversation)
        db.flush()
        greeting = ai.greeting if ai else 'Здравствуйте! Помогу выбрать услугу и время приёма.'
        append_message(db, conversation, 'assistant', greeting + '\nНе присылайте диагнозы, снимки и медицинские документы. На медицинские вопросы ответит специалист.')
    elif patient and not conversation.patient_id:
        conversation.patient_id = patient.id
    return conversation


def payload(db, conversation):
    messages = list(db.scalars(select(m.Message).where(m.Message.tenant_id == conversation.tenant_id,
        m.Message.conversation_id == conversation.id).order_by(m.Message.created_at.desc()).limit(100)))
    return {'conversation':serial(conversation,db),'messages':[serial(x) for x in reversed(messages)],
            'options':(conversation.context or {}).get('options',menu()),'mode':'demo'}


def request_human_assistance(db, tenant, conversation, reason='Пациент просит подключить сотрудника'):
    conversation.mode = 'human'
    conversation.context = {**(conversation.context or {}),'options':[option('Мои записи','appointments')]}
    key = f'handoff:{conversation.id}'
    existing = db.scalar(select(m.Task).where(m.Task.tenant_id == tenant.id, m.Task.dedup_key == key))
    if existing:
        existing.status = 'open'
    else:
        db.add(m.Task(tenant_id=tenant.id, patient_id=conversation.patient_id, title='Подключиться к диалогу',
            description=reason, due_at=utcnow(), dedup_key=key))
    audit(db,tenant.id,None,'conversation.handoff','conversation',conversation.id)


def _patient(db,tenant,conversation,visitor=None,user=None):
    if conversation.patient_id:
        return tenant_item(db,m.Patient,conversation.patient_id,tenant.id)
    if visitor:
        return identity_patient(db,tenant,visitor,user,create=False)
    return None


def _own_appointment(db,tenant,conversation,item_id,visitor,user):
    patient = _patient(db,tenant,conversation,visitor,user)
    appointment = tenant_item(db,m.Appointment,str(item_id),tenant.id)
    if not patient or appointment.patient_id != patient.id:
        raise HTTPException(404,'Запись не найдена в вашем профиле')
    return appointment


def _offer_slots(db,tenant,context):
    service_id,doctor_id,branch_id = (context.get(x) for x in ['service_id','doctor_id','branch_id'])
    today = utcnow().astimezone(ZoneInfo(tenant.timezone)).date()
    slots = []
    for offset in range(7):
        slots = available_slots(db,tenant,service_id,today+timedelta(days=offset),doctor_id,branch_id)
        if slots:
            break
    if not slots:
        return 'В ближайшие 7 дней свободных интервалов нет. Администратор поможет подобрать другую дату.', [option('Позвать администратора','human'),*menu()[:1]]
    options = []
    for slot in slots[:8]:
        dt=datetime.fromisoformat(slot['start_at']).astimezone(ZoneInfo(tenant.timezone))
        options.append(option(dt.strftime('%d.%m в %H:%M'),'select_slot',start_at=slot['start_at']))
    return 'Доступное время из расписания клиники. Выберите подходящий интервал:', options


def handle_message(db, tenant, conversation, message, action=None, data=None, visitor=None, user=None, classify_external=True, preclassification=None):
    if conversation.tenant_id != tenant.id:
        raise HTTPException(404,'Диалог не найден')
    # Optional conservative intent classification happens BEFORE row locks / writes.
    # Only a closed administrative vocabulary is eligible; patient data stays local.
    ai = db.scalar(select(m.AISettings).where(m.AISettings.tenant_id == tenant.id))
    completion = None
    if preclassification is not None and not action:
        intent,completion=preclassification
        action={'hours':'clinic_info','greeting':'help','unknown':None}.get(intent,intent)
    if preclassification is None and classify_external and not action and ai and ai.enabled and ai.provider != 'demo' and conversation.mode == 'ai':
        subscription=db.scalar(select(m.Subscription).where(m.Subscription.tenant_id==tenant.id))
        plan=db.scalar(select(m.Plan).where(m.Plan.code==subscription.plan_code)) if subscription else None
        month_start=utcnow().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        usage=db.scalar(select(func.count(m.AIUsage.id)).where(m.AIUsage.tenant_id==tenant.id,m.AIUsage.provider!='demo',m.AIUsage.created_at>=month_start)) or 0
        if plan and usage<plan.ai_limit:
            from ..adapters.ai import safe_intent
            intent, completion = safe_intent(message or '', ai.provider)
            action = {'hours':'clinic_info','greeting':'help','unknown':None}.get(intent, intent)
    # Lock the conversation so rapid repeated clicks do not create overlapping state transitions.
    db.scalar(select(m.Conversation).where(m.Conversation.id == conversation.id,
        m.Conversation.tenant_id == tenant.id).with_for_update())
    context = dict(conversation.context or {})
    channel_context = {k:v for k,v in context.items() if k.startswith('telegram_')}
    data = data or {}
    message = (message or '').strip()[:3000]
    action = action or ''
    if message:
        append_message(db,conversation,'patient',message)
    lead = db.scalar(select(m.Lead).where(m.Lead.tenant_id == tenant.id,m.Lead.conversation_id == conversation.id))
    if not lead and not conversation.patient_id:
        db.add(m.Lead(tenant_id=tenant.id,conversation_id=conversation.id,title='Обращение из чата',source=conversation.channel))
    text_lower = message.lower()
    if not action:
        if text_lower in ['/start','/help']:
            action='help'
        elif text_lower == '/book' or any(x in text_lower for x in ['записать','записаться','хочу запись']):
            action='book'
        elif text_lower == '/appointments' or 'мои записи' in text_lower:
            action='appointments'
        elif text_lower == '/human' or any(x in text_lower for x in ['оператор','живой человек','позвать администратора']):
            action='human'
        elif any(x in text_lower for x in ['цен','стоим','прайс','услуг']):
            action='services'
        elif 'врач' in text_lower:
            action='doctors'
        elif any(x in text_lower for x in ['адрес','филиал','где наход','парков','оплат','как добраться','правила визита']):
            action='clinic_info'
    medical = bool(re.search(r'лекарств|таблет|антибиот|диагноз|лечить|лечени[ея] дома|болит|кровотеч|опух|температур',text_lower))
    ai = db.scalar(select(m.AISettings).where(m.AISettings.tenant_id == tenant.id))
    options=menu()
    if action=='human' or medical:
        request_human_assistance(db,tenant,conversation,'Медицинский вопрос' if medical else 'Пациент просит сотрудника')
        text='Я передал обращение сотруднику клиники. Вопросы о симптомах, диагнозе и лечении решает медицинский специалист. Ответ сотрудника появится в этом диалоге.'
        if medical:
            text+=' При угрожающем жизни состоянии звоните 112.'
        options=[option('Мои записи','appointments')]
        context={**context,'stage':'human'}
    elif (conversation.mode=='human' or (ai and not ai.enabled)) and action not in {'appointments','confirm_cancel','cancel_appointment','confirm_appointment'}:
        if conversation.mode!='human':
            request_human_assistance(db,tenant,conversation,'AI отключён в настройках клиники')
        text='Сообщение сохранено для администратора. Он ответит здесь; автоматические ответы на вопросы отключены.'
        options=[option('Мои записи','appointments')]
    elif action in {'book','services'}:
        services=list(db.scalars(select(m.Service).where(m.Service.tenant_id==tenant.id,m.Service.active.is_(True)).order_by(m.Service.name)))
        text='Выберите услугу. Указан актуальный прайс клиники; окончательный план лечения определяет врач.'
        options=[option(f'{s.name} · {s.price_kopecks/100:,.0f} ₽'.replace(',',' '),'select_service',service_id=s.id) for s in services]
        context={'stage':'service'}
    elif action=='select_service':
        service=tenant_item(db,m.Service,str(data.get('service_id','')),tenant.id)
        context={'stage':'branch','service_id':service.id,'booking_key':uid()}
        branch_ids=select(m.Doctor.branch_id).join(m.DoctorService,m.DoctorService.doctor_id==m.Doctor.id).where(
            m.Doctor.tenant_id==tenant.id,m.DoctorService.tenant_id==tenant.id,m.Doctor.active.is_(True),m.DoctorService.service_id==service.id)
        branches=list(db.scalars(select(m.Branch).where(m.Branch.tenant_id==tenant.id,m.Branch.active.is_(True),m.Branch.id.in_(branch_ids))))
        text=f'{service.name}: {service.price_kopecks/100:,.0f} ₽, {service.duration_minutes} мин. Выберите филиал.'.replace(',',' ')
        options=[option(b.name,'select_branch',branch_id=b.id) for b in branches]
    elif action=='select_branch':
        if not context.get('service_id'):
            raise HTTPException(409,'Сначала выберите услугу')
        branch=tenant_item(db,m.Branch,str(data.get('branch_id','')),tenant.id)
        context.update(stage='doctor',branch_id=branch.id)
        doctors=list(db.scalars(select(m.Doctor).join(m.DoctorService,m.DoctorService.doctor_id==m.Doctor.id).where(
            m.Doctor.tenant_id==tenant.id,m.DoctorService.tenant_id==tenant.id,m.Doctor.branch_id==branch.id,
            m.Doctor.active.is_(True),m.DoctorService.service_id==context['service_id'])).unique())
        text='К кому хотите записаться?' if doctors else 'В этом филиале нет врача по выбранной услуге. Выберите другую услугу.'
        options=[option(f'{d.name} · {d.specialty}','select_doctor',doctor_id=d.id) for d in doctors] or menu()
    elif action=='select_doctor':
        if not context.get('service_id') or not context.get('branch_id'):
            raise HTTPException(409,'Сначала выберите услугу и филиал')
        doctor=tenant_item(db,m.Doctor,str(data.get('doctor_id','')),tenant.id)
        context.update(doctor_id=doctor.id,stage='slot')
        text,options=_offer_slots(db,tenant,context)
    elif action=='select_slot':
        if not context.get('doctor_id'):
            raise HTTPException(409,'Сначала выберите врача')
        try:
            chosen=datetime.fromisoformat(str(data['start_at']))
            if chosen.tzinfo is None:
                raise ValueError
        except (KeyError,ValueError):
            raise HTTPException(422,'Некорректное время')
        slots=available_slots(db,tenant,context['service_id'],chosen.astimezone(ZoneInfo(tenant.timezone)).date(),context['doctor_id'],context['branch_id'])
        if not any(datetime.fromisoformat(s['start_at'])==chosen for s in slots):
            raise HTTPException(409,'Это время больше не свободно. Начните выбор времени снова.')
        context.update(start_at=chosen.isoformat())
        if context.get('reschedule_id'):
            context['stage']='reschedule_confirm'
            text='Подтвердите перенос на '+chosen.astimezone(ZoneInfo(tenant.timezone)).strftime('%d.%m в %H:%M')+'.'
            options=[option('Подтвердить перенос','confirm_reschedule')]
        else:
            context['stage']='contact'
            text='Напишите имя и телефон одним сообщением, например: Тестовый Пациент, +7 900 000-00-00. Для демонстрации используйте вымышленные данные.' if tenant.is_demo else 'Напишите имя и телефон одним сообщением. Не отправляйте медицинские документы.'
            options=[]
    elif action=='confirm_booking':
        if context.get('stage') not in {'consent','booked'} or not all(context.get(x) for x in ['patient_name','phone','start_at','service_id','doctor_id','branch_id','booking_key']):
            raise HTTPException(409,'Сначала выберите время и укажите контактные данные')
        if data.get('consent_pd') is not True:
            raise HTTPException(422,'Подтвердите согласие на обработку данных для записи')
        notifications=data.get('consent_notifications') is True
        patient=_patient(db,tenant,conversation,visitor,user)
        if not patient:
            if visitor:
                patient=identity_patient(db,tenant,visitor,user,context['patient_name'],context['phone'],notifications,create=True)
            else:
                patient=m.Patient(tenant_id=tenant.id,name=context['patient_name'],phone=context['phone'],notifications_enabled=notifications)
                db.add(patient); db.flush()
        save_consents(db,tenant.id,patient,True,notifications,conversation.channel)
        appointment=create_appointment(db,tenant,patient,context['service_id'],context['doctor_id'],context['branch_id'],
            datetime.fromisoformat(context['start_at']),context['booking_key'],conversation.id,conversation.channel,
            conversation_id=conversation.id)
        conversation.patient_id=patient.id
        context['stage']='booked'
        text='Запись подтверждена системой: '+aware(appointment.start_at).astimezone(ZoneInfo(tenant.timezone)).strftime('%d.%m.%Y в %H:%M')+'. Она уже появилась в расписании администратора.'
        options=[option('Мои записи','appointments'),option('Записаться ещё','book')]
    elif action=='appointments':
        patient=_patient(db,tenant,conversation,visitor,user)
        appointments=list(db.scalars(select(m.Appointment).where(m.Appointment.tenant_id==tenant.id,
            m.Appointment.patient_id==patient.id).order_by(m.Appointment.start_at.desc()).limit(10))) if patient else []
        text='Ваших записей пока нет. Запишитесь здесь или на сайте клиники.' if not appointments else 'Записи, связанные с вашей подтверждённой сессией:'
        options=[]
        for a in appointments:
            when=aware(a.start_at).astimezone(ZoneInfo(tenant.timezone)).strftime('%d.%m %H:%M')
            labels={'scheduled':'записан','confirmed':'подтверждён','cancelled':'отменён','completed':'завершён','no_show':'не состоялся'}
            text+=f'\n• {when} — {labels.get(a.status,a.status)}'
            if a.status in {'scheduled','confirmed'} and aware(a.start_at)>utcnow():
                options.extend([option('Перенести '+when,'reschedule',appointment_id=a.id),
                                option('Отменить '+when,'cancel_appointment',appointment_id=a.id)])
                if a.status=='scheduled':
                    options.append(option('Подтвердить '+when,'confirm_appointment',appointment_id=a.id))
        options.append(option('Записаться','book'))
    elif action=='reschedule':
        appointment=_own_appointment(db,tenant,conversation,data.get('appointment_id'),visitor,user)
        context={'reschedule_id':appointment.id,'service_id':appointment.service_id,'doctor_id':appointment.doctor_id,'branch_id':appointment.branch_id,'stage':'slot'}
        text,options=_offer_slots(db,tenant,context)
    elif action=='confirm_reschedule':
        appointment=_own_appointment(db,tenant,conversation,context.get('reschedule_id'),visitor,user)
        change_appointment(db,tenant,appointment,action='reschedule',start_at=datetime.fromisoformat(context['start_at']))
        context={}
        text='Запись перенесена. Старое время освобождено, новое сохранено в расписании.'
        options=[option('Мои записи','appointments')]
    elif action=='cancel_appointment':
        appointment=_own_appointment(db,tenant,conversation,data.get('appointment_id'),visitor,user)
        text='Отменить выбранный визит? Это освободит время в расписании.'
        options=[option('Да, отменить запись','confirm_cancel',appointment_id=appointment.id),option('Сохранить запись','appointments')]
    elif action in {'confirm_cancel','confirm_appointment'}:
        appointment=_own_appointment(db,tenant,conversation,data.get('appointment_id'),visitor,user)
        change_appointment(db,tenant,appointment,action='cancel' if action=='confirm_cancel' else 'confirm')
        text='Запись отменена.' if action=='confirm_cancel' else 'Визит подтверждён. Будем ждать вас!'
        options=[option('Мои записи','appointments'),option('Выбрать новое время','book')]
    elif action=='doctors':
        doctors=list(db.scalars(select(m.Doctor).where(m.Doctor.tenant_id==tenant.id,m.Doctor.active.is_(True))))
        text='Наши специалисты:\n'+'\n'.join(f'• {d.name} — {d.specialty}' for d in doctors)
        options=[option('Выбрать услугу и записаться','book')]
    elif action=='clinic_info':
        branches=list(db.scalars(select(m.Branch).where(m.Branch.tenant_id==tenant.id,m.Branch.active.is_(True))))
        text=tenant.name+'\n'+tenant.description+'\n'+'\n'.join(f'{b.name}: {b.address}' for b in branches)+'\nТелефон: '+tenant.phone+'\n'+(ai.clinic_knowledge if ai else '')
    elif not action and context.get('stage')=='contact':
        match=re.search(r'(?:\+?\d[\d\s()\-]{8,}\d)',message)
        if not match:
            text='Нужны имя и телефон с кодом страны, например: Тестовый Пациент, +7 900 000-00-00.'
            options=[]
        else:
            try:
                phone=validate_phone(match.group())
            except ValueError as e:
                raise HTTPException(422,str(e))
            name=message[:match.start()].strip(' ,.;:') or message[match.end():].strip(' ,.;:')
            if len(name)<2 or len(name)>160:
                raise HTTPException(422,'Укажите имя перед номером телефона')
            context.update(patient_name=name,phone=phone,stage='consent')
            text='Для записи клиника обработает ваше имя и телефон. Подтверждая запись, вы даёте согласие на обработку этих данных для организации визита (версия согласия 2026-11-05). Напоминания включаются отдельно. Медицинские данные не нужны.'
            options=[option('Согласен: записаться без напоминаний','confirm_booking',consent_pd=True,consent_notifications=False),
                     option('Согласен: записаться с напоминаниями','confirm_booking',consent_pd=True,consent_notifications=True)]
    else:
        text='Помогу с услугами, актуальными ценами, врачами и свободным временем. Выберите действие ниже. По медицинским вопросам подключу сотрудника.'
    context['options']=options
    conversation.context={**channel_context,**context}
    append_message(db,conversation,'assistant',text)
    db.add(m.AIUsage(tenant_id=tenant.id,provider=completion.provider if completion else 'demo',
        input_tokens=completion.input_tokens if completion else 0,
        output_tokens=completion.output_tokens if completion else 0,cost_kopecks=None if completion else 0,success=True))
    db.flush()
    return payload(db,conversation)
