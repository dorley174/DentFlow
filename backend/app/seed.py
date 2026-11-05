"""Reproducible synthetic Dev Stand. This module refuses production databases."""
from datetime import datetime, time, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete
from .config import settings
from .db import SessionLocal, utcnow, uid
from . import models as m
from .security import hash_password

DEMO_ACCOUNTS = {
    'super':('Super-Demo-2026!', 'super_admin', 'Владелец DentFlow'),
    'owner':('Owner-Demo-2026!', 'owner', 'Мария Волкова'),
    'manager':('Manager-Demo-2026!', 'manager', 'Елена Миронова'),
    'admin':('Admin-Demo-2026!', 'administrator', 'Анна Смирнова'),
    'doctor':('Doctor-Demo-2026!', 'doctor', 'Александр Морозов'),
    'patient':('Patient-Demo-2026!', 'patient', 'Тестовый Пациент'),
}


def assert_demo_database():
    name = urlparse(settings.database_url).path.lstrip('/')
    if settings.app_env == 'test':
        if settings.database_url.startswith('sqlite') or name == 'dentflow_test':
            return
        raise RuntimeError('Тесты и тестовый seed разрешены только в отдельной БД dentflow_test')
    if settings.app_env not in {'development','devstand'} or not settings.enable_dev_tools or name not in {'dentflow_dev','dentflow_devstand','dentflow_test'}:
        raise RuntimeError('Сброс и seed разрешены только в dev/test, при ENABLE_DEV_TOOLS=true и отдельной БД dentflow_dev/dentflow_devstand/dentflow_test')


def seed_plans(db):
    data=[('START','Старт',590000,1,0,['Онлайн-запись','Базовая CRM','Веб-чат']),
          ('BUSINESS','Бизнес',1490000,2,10000,['AI-администратор','Telegram','Автоматизации','Аналитика']),
          ('ENTERPRISE','Сеть клиник',2990000,20,50000,['Несколько филиалов','Индивидуальные настройки','Приоритетная поддержка'])]
    for code,name,price,branches,limit,features in data:
        if not db.scalar(select(m.Plan).where(m.Plan.code==code)):
            db.add(m.Plan(code=code,name=name,price_kopecks=price,branch_limit=branches,ai_limit=limit,features=features))
    db.flush()


def seed_clinic(db, slug='smile-avenue', full=True):
    tenant=m.Tenant(name='Smile Avenue' if full else 'Аврора Дент',slug=slug,is_demo=True,
        description='Демонстрационная стоматология. Все данные вымышлены; реальные обращения не отправляются.',
        phone='+7 000 000-00-00',brand_color='#0D9488')
    db.add(tenant); db.flush()
    branches=[]
    for name,address in [('Центральный','Демо-город, ул. Светлая, 12'),('Северный','Демо-город, проспект Мира, 48')]:
        branch=m.Branch(tenant_id=tenant.id,name=name,address=address,phone='+7 000 000-00-00')
        db.add(branch); branches.append(branch)
    db.flush()
    doctor_names=[('Александр Морозов','Стоматолог-терапевт','#0D9488'),('Екатерина Лебедева','Стоматолог-ортодонт','#6366F1'),
                  ('Михаил Соколов','Стоматолог-хирург','#E69A38'),('Дарья Белова','Стоматолог-гигиенист','#D772A9'),
                  ('Артём Кузнецов','Стоматолог-ортопед','#3C91D4')]
    doctors=[]
    for i,(name,specialty,color) in enumerate(doctor_names):
        doctor=m.Doctor(tenant_id=tenant.id,name=name,specialty=specialty,color=color,branch_id=branches[i%2].id)
        db.add(doctor); doctors.append(doctor)
    db.flush()
    catalog=[('Консультация стоматолога','Диагностика',30,150000),('Профессиональная гигиена','Профилактика',60,550000),
             ('Лечение кариеса','Терапия',60,650000),('Консультация ортодонта','Ортодонтия',45,200000),
             ('Консультация хирурга','Хирургия',30,200000),('Консультация ортопеда','Ортопедия',45,250000),
             ('Панорамный снимок','Диагностика',30,180000),('Компьютерная томография','Диагностика',30,350000),
             ('Профилактический осмотр','Профилактика',30,120000),('Герметизация фиссур','Профилактика',45,350000),
             ('Эстетическая реставрация','Терапия',90,1200000),('Подбор плана протезирования','Ортопедия',60,350000)]
    services=[]
    for name,category,duration,price in catalog:
        service=m.Service(tenant_id=tenant.id,name=name,category=category,duration_minutes=duration,price_kopecks=price,
                          description='Пример услуги демонстрационной клиники. Объём работ определяет врач.')
        db.add(service); services.append(service)
    db.flush()
    service_map={0:[0,2,6,7,8,10],1:[0,3,6,7,8],2:[0,4,6,7,8],3:[0,1,8,9],4:[0,5,6,7,8,11]}
    for i,doctor in enumerate(doctors):
        for j in service_map[i]:
            db.add(m.DoctorService(tenant_id=tenant.id,doctor_id=doctor.id,service_id=services[j].id))
        for weekday in range(7):
            db.add(m.Schedule(tenant_id=tenant.id,doctor_id=doctor.id,branch_id=doctor.branch_id,
                weekday=weekday,start_time='09:00',end_time='19:00' if weekday<5 else '17:00',break_start='13:00',break_end='14:00'))
    patients=[]
    names=['Анна Соколова','Дмитрий Петров','Елена Крылова','Алексей Иванов','Мария Орлова','Николай Васильев',
           'Полина Зайцева','Илья Козлов','Виктория Попова','Олег Волков','Софья Павлова','Роман Фёдоров',
           'Алина Семёнова','Максим Егоров','Наталья Никитина','Павел Андреев','Ольга Макарова','Денис Николаев',
           'Вера Степанова','Игорь Михайлов','Юлия Алексеева','Кирилл Григорьев','Татьяна Романова','Вадим Захаров',
           'Евгения Борисова','Сергей Королёв','Ксения Герасимова','Антон Киселёв','Людмила Матвеева','Тестовый Пациент']
    for i,name in enumerate(names if full else names[:3]):
        patient=m.Patient(tenant_id=tenant.id,name=name+' (демо)' if i<29 else name,
            phone=f'+7000000{i:04d}',notifications_enabled=True,
            marketing_enabled=False,segment=['Новый пациент','Постоянный','Ожидает визита'][i%3])
        db.add(patient); patients.append(patient)
    db.flush()
    users=[]
    if full:
        for login,(password,role,name) in DEMO_ACCOUNTS.items():
            if role=='super_admin':
                continue
            user=m.User(tenant_id=tenant.id,email=f'{login}@dentflow.local',name=name,role=role,password_hash=hash_password(password),
                doctor_id=doctors[0].id if role=='doctor' else None,patient_id=patients[-1].id if role=='patient' else None)
            db.add(user);users.append(user)
    else:
        db.add(m.User(tenant_id=tenant.id,email='other@dentflow.local',name='Администратор второй клиники',
                      role='administrator',password_hash=hash_password('Other-Demo-2026!')))
    db.flush()
    tz=ZoneInfo(tenant.timezone)
    today=utcnow().astimezone(tz).date()
    for i in range(20 if full else 2):
        doctor=doctors[i%5]
        service=services[0]
        # 5 simultaneous doctors per day, one visit each; tomorrow to +4 days.
        day=today+timedelta(days=1+i//5)
        start=datetime.combine(day,time(10+(i%2),0),tzinfo=tz)
        appointment=m.Appointment(tenant_id=tenant.id,patient_id=patients[i%len(patients)].id,
            doctor_id=doctor.id,service_id=service.id,branch_id=doctor.branch_id,start_at=start,
            end_at=start+timedelta(minutes=30),price_kopecks=service.price_kopecks,
            status='confirmed' if i%3==0 else 'scheduled',source=['web','telegram','manual'][i%3],idempotency_key='seed-'+str(i))
        db.add(appointment)
        db.add(m.Lead(tenant_id=tenant.id,patient_id=patients[i%len(patients)].id,title=service.name,
            stage='Подтверждён' if i%3==0 else 'Записан',source=appointment.source,
            amount_kopecks=service.price_kopecks,summary='Демонстрационная запись, пациент выбрал свободное время.'))
    if full:
        for i in range(20,27):
            db.add(m.Lead(tenant_id=tenant.id,patient_id=patients[i].id,title=['Консультация','Гигиена','Вопрос о расписании'][i%3],
                stage=['Новое обращение','Не обработано','В работе','Консультация','Предложено время','Завершено','Потерян'][i-20],
                source='web',amount_kopecks=150000,summary='Синтетический пример CRM.'))
        for i in range(4):
            conv=m.Conversation(tenant_id=tenant.id,patient_id=patients[i].id,channel='web' if i%2==0 else 'telegram',
                mode='human' if i==1 else 'ai',context={})
            db.add(conv);db.flush()
            db.add(m.Message(tenant_id=tenant.id,conversation_id=conv.id,role='patient',text=['Здравствуйте! Хочу записаться на консультацию.','Можно узнать стоимость гигиены?','Спасибо, время подходит.','Как найти ваш филиал?'][i]))
            db.add(m.Message(tenant_id=tenant.id,conversation_id=conv.id,role='assistant',text='Здравствуйте! Помогу с организацией визита. Это демонстрационная переписка.'))
        for i,title in enumerate(['Подтвердить завтрашние визиты','Ответить на вопрос о гигиене','Проверить новые обращения','Лист ожидания']):
            db.add(m.Task(tenant_id=tenant.id,title=title,description='Задача из демонстрационного набора.',
                patient_id=patients[i].id,due_at=utcnow()+timedelta(hours=i+1),status='in_progress' if i==1 else 'open'))
    for name,kind,minutes,enabled in [('Накануне визита','reminder',1440,True),('За 2 часа до визита','reminder',120,True),
        ('Пациент перестал отвечать','missed_reply',60,True),('Обратная связь после визита','feedback',1440,True),
        ('Реактивация с маркетинговым согласием','reactivation',86400,False),('Лист ожидания: задача сотруднику','waitlist',60,True)]:
        db.add(m.AutomationRule(tenant_id=tenant.id,name=name,kind=kind,delay_minutes=minutes,enabled=enabled))
    db.add(m.AISettings(tenant_id=tenant.id,provider='demo',greeting='Здравствуйте! Я администратор Smile Avenue. Помогу выбрать услугу и удобное время.',
                       clinic_knowledge='Оплата по прайсу. По вопросам диагностики и лечения подключается сотрудник.'))
    for name,kind,status,description in [('Встроенное расписание','internal','connected','Запись в PostgreSQL DentFlow'),
        ('Telegram','telegram','not_connected','Нужен токен собственного бота и запуск сервиса telegram'),
        ('1С:Медицина','mis_1c','planned','Интерфейс адаптера; доступ и лицензии проверяются отдельно'),
        ('IDENT','mis_ident','planned','Адаптер не реализован'),('Инфодент','mis_infodent','planned','Адаптер не реализован'),
        ('ЮKassa / СБП','payments','demo','DEMO: деньги не списываются')]:
        db.add(m.Integration(tenant_id=tenant.id,name=name,kind=kind,status=status,description=description))
    db.add(m.Subscription(tenant_id=tenant.id,plan_code='BUSINESS',status='demo',payment_mode='DEMO'))
    db.add(m.AuditLog(tenant_id=tenant.id,actor_id=None,action='demo.seeded',entity_type='tenant',entity_id=tenant.id,
        details={'synthetic':True,'patients':len(patients)}))
    db.flush()
    return tenant


def seed_demo(db):
    assert_demo_database()
    seed_plans(db)
    if not db.scalar(select(m.User).where(m.User.role=='super_admin')):
        password,role,name=DEMO_ACCOUNTS['super']
        db.add(m.User(tenant_id=None,email='super@dentflow.local',name=name,role=role,password_hash=hash_password(password)))
    if not db.scalar(select(m.Tenant).where(m.Tenant.slug=='smile-avenue')):
        seed_clinic(db)
    if not db.scalar(select(m.Tenant).where(m.Tenant.slug=='aurora-dental')):
        seed_clinic(db,'aurora-dental',False)
    db.flush()


def reset_demo(db):
    assert_demo_database()
    tenant=db.scalar(select(m.Tenant).where(m.Tenant.slug=='smile-avenue').with_for_update())
    if tenant and not tenant.is_demo:
        raise RuntimeError('Сброс реальной клиники запрещён')
    if tenant:
        db.delete(tenant);db.flush()
    return seed_clinic(db)


if __name__=='__main__':
    assert_demo_database()
    with SessionLocal() as db:
        seed_demo(db)
        db.commit()
    print('Демонстрационные данные готовы. Аккаунты: DEV_STAND.md. Все пациенты вымышлены.')
