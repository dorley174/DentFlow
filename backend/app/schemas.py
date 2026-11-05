from datetime import datetime
from typing import Literal
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def validate_phone(value: str) -> str:
    digits = re.sub(r'\D', '', value)
    if len(digits) == 11 and digits[0] == '8':
        digits = '7' + digits[1:]
    if not (10 <= len(digits) <= 15):
        raise ValueError('Введите телефон с кодом страны, например +7 900 000-00-00')
    return '+' + digits


def validate_datetime(value):
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError('Время должно включать часовой пояс, например +03:00')
    return value


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class BookingInput(Input):
    service_id: str = Field(max_length=36)
    doctor_id: str = Field(max_length=36)
    branch_id: str = Field(max_length=36)
    start_at: datetime
    patient_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=10, max_length=30)
    consent_pd: Literal[True]
    consent_notifications: bool = False
    idempotency_key: str = Field(min_length=8, max_length=100)
    _phone = field_validator('phone')(validate_phone)
    _tz = field_validator('start_at')(validate_datetime)


class AdminBookingInput(Input):
    service_id: str = Field(max_length=36)
    doctor_id: str = Field(max_length=36)
    branch_id: str = Field(max_length=36)
    start_at: datetime
    patient_id: str | None = None
    patient_name: str | None = Field(None, min_length=2, max_length=160)
    phone: str | None = Field(None, max_length=30)
    consent_pd: Literal[True] = True
    consent_notifications: bool = False
    idempotency_key: str = Field(min_length=8, max_length=100)
    _tz = field_validator('start_at')(validate_datetime)
    @model_validator(mode='after')
    def patient(self):
        if not self.patient_id and not (self.patient_name and self.phone):
            raise ValueError('Выберите пациента или укажите имя и телефон')
        if self.phone:
            self.phone = validate_phone(self.phone)
        return self


AppointmentStatus = Literal['scheduled', 'confirmed', 'completed', 'cancelled', 'no_show']


class AppointmentPatch(Input):
    action: Literal['cancel', 'reschedule', 'confirm'] | None = None
    status: AppointmentStatus | None = None
    start_at: datetime | None = None
    _tz = field_validator('start_at')(validate_datetime)
    @model_validator(mode='after')
    def nonempty(self):
        if not (self.action or self.status or self.start_at):
            raise ValueError('Укажите действие или статус')
        if self.action == 'reschedule' and self.start_at is None:
            raise ValueError('Укажите новое время')
        return self


class ChatInput(Input):
    message: str = Field(default='', max_length=3000)
    action: str | None = Field(default=None, max_length=40)
    data: dict = Field(default_factory=dict)
    @model_validator(mode='after')
    def limits(self):
        if not self.message and not self.action:
            raise ValueError('Напишите сообщение')
        if len(str(self.data)) > 5000:
            raise ValueError('Слишком много данных')
        return self


class BranchInput(Input):
    name: str = Field(min_length=2, max_length=160)
    address: str = Field(default='', max_length=500)
    phone: str = Field(default='', max_length=30)
    active: bool = True


class BranchPatch(Input):
    name: str | None = Field(None, min_length=2, max_length=160)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=30)
    active: bool | None = None


class DoctorInput(Input):
    name: str = Field(min_length=2, max_length=160)
    specialty: str = Field(default='Стоматолог', min_length=2, max_length=160)
    branch_id: str
    color: str = Field(default='#0D9488', pattern=r'^#[0-9a-fA-F]{6}$')
    active: bool = True
    service_ids: list[str] = Field(default_factory=list, max_length=100)


class DoctorPatch(Input):
    name: str | None = Field(None, min_length=2, max_length=160)
    specialty: str | None = Field(None, min_length=2, max_length=160)
    branch_id: str | None = None
    color: str | None = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')
    active: bool | None = None
    service_ids: list[str] | None = Field(None, max_length=100)


class ServiceInput(Input):
    name: str = Field(min_length=2, max_length=200)
    category: str = Field(default='Стоматология', min_length=2, max_length=100)
    description: str = Field(default='', max_length=4000)
    duration_minutes: int = Field(default=30, ge=15, le=480, multiple_of=15)
    price_kopecks: int = Field(default=0, ge=0, le=1000000000)
    active: bool = True


class ServicePatch(Input):
    name: str | None = Field(None, min_length=2, max_length=200)
    category: str | None = Field(None, min_length=2, max_length=100)
    description: str | None = Field(None, max_length=4000)
    duration_minutes: int | None = Field(None, ge=15, le=480, multiple_of=15)
    price_kopecks: int | None = Field(None, ge=0, le=1000000000)
    active: bool | None = None


class ScheduleInput(Input):
    doctor_id: str
    branch_id: str
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(default='09:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    end_time: str = Field(default='18:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    break_start: str | None = Field(default=None, pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    break_end: str | None = Field(default=None, pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    active: bool = True
    @model_validator(mode='after')
    def time_order(self):
        if self.start_time >= self.end_time:
            raise ValueError('Начало смены должно быть раньше окончания')
        if bool(self.break_start) != bool(self.break_end):
            raise ValueError('Укажите начало и конец перерыва')
        if self.break_start and not (self.start_time <= self.break_start < self.break_end <= self.end_time):
            raise ValueError('Перерыв должен находиться внутри рабочей смены')
        return self


class SchedulePatch(Input):
    doctor_id: str | None = None
    branch_id: str | None = None
    weekday: int | None = Field(None, ge=0, le=6)
    start_time: str | None = None
    end_time: str | None = None
    break_start: str | None = None
    break_end: str | None = None
    active: bool | None = None


Stage = Literal['Новое обращение','Не обработано','В работе','Консультация','Предложено время','Записан','Подтверждён','Посетил','Завершено','Потерян']


class LeadInput(Input):
    title: str = Field(min_length=2, max_length=200)
    patient_id: str | None = None
    stage: Stage = 'Новое обращение'
    source: Literal['web','telegram','manual','demo'] = 'manual'
    assigned_to: str | None = None
    summary: str = Field(default='', max_length=4000)
    amount_kopecks: int = Field(default=0, ge=0)


class LeadPatch(Input):
    title: str | None = Field(None, min_length=2, max_length=200)
    stage: Stage | None = None
    assigned_to: str | None = None
    summary: str | None = Field(None, max_length=4000)
    amount_kopecks: int | None = Field(None, ge=0)


class TaskInput(Input):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default='', max_length=4000)
    status: Literal['open','in_progress','done'] = 'open'
    due_at: datetime | None = None
    assigned_to: str | None = None
    patient_id: str | None = None
    _tz = field_validator('due_at')(validate_datetime)


class TaskPatch(Input):
    title: str | None = Field(None, min_length=2, max_length=200)
    description: str | None = Field(None, max_length=4000)
    status: Literal['open','in_progress','done'] | None = None
    due_at: datetime | None = None
    assigned_to: str | None = None
    patient_id: str | None = None
    _tz = field_validator('due_at')(validate_datetime)


class EmployeeInput(Input):
    name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=12, max_length=128)
    role: Literal['manager','administrator','doctor']
    doctor_id: str | None = None
    active: bool = True


class EmployeePatch(Input):
    name: str | None = Field(None, min_length=2, max_length=160)
    email: str | None = Field(None, min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str | None = Field(None, min_length=12, max_length=128)
    role: Literal['manager','administrator','doctor'] | None = None
    doctor_id: str | None = None
    active: bool | None = None


class AutomationInput(Input):
    name: str = Field(min_length=2, max_length=200)
    kind: Literal['reminder','missed_reply','feedback','reactivation','waitlist']
    enabled: bool = True
    delay_minutes: int = Field(default=120, ge=1, le=525600)


class AutomationPatch(Input):
    name: str | None = Field(None, min_length=2, max_length=200)
    enabled: bool | None = None
    delay_minutes: int | None = Field(None, ge=1, le=525600)


class TenantPatch(Input):
    name: str | None = Field(None, min_length=2, max_length=160)
    description: str | None = Field(None, max_length=4000)
    phone: str | None = Field(None, max_length=30)
    brand_color: str | None = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')
    logo_url: str | None = Field(None, max_length=500)


class AISettingsPatch(Input):
    provider: Literal['demo','yandex','gigachat','local'] | None = None
    enabled: bool | None = None
    greeting: str | None = Field(None, min_length=2, max_length=1000)
    clinic_knowledge: str | None = Field(None, max_length=20000)
    handoff_medical: Literal[True] | None = None


class SettingsPatch(Input):
    tenant: TenantPatch | None = None
    ai_settings: AISettingsPatch | None = None


class ConversationPatch(Input):
    mode: Literal['human','ai']


class MessageInput(Input):
    text: str = Field(min_length=1, max_length=3000)


class RunAutomations(Input):
    advance_minutes: int = Field(default=0, ge=0, le=525600)


class SimulateInput(RunAutomations):
    event: Literal['new_lead','cancel','missed_reply','task','free_slot','reminder','handoff']


class ResetInput(Input):
    confirmation: Literal['RESET SMILE AVENUE']


class TenantInput(Input):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=3, max_length=80, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    phone: str = Field(default='', max_length=30)
    owner_name: str = Field(min_length=2, max_length=160)
    owner_email: str = Field(min_length=5, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    owner_password: str = Field(min_length=12, max_length=128)
    plan_code: Literal['START','BUSINESS','ENTERPRISE'] = 'BUSINESS'


class SuperTenantPatch(Input):
    name: str | None = Field(None, min_length=2, max_length=160)
    status: Literal['active','blocked'] | None = None
    plan_code: Literal['START','BUSINESS','ENTERPRISE'] | None = None


class PlanPatch(Input):
    price_kopecks: int | None = Field(None, ge=0, le=1000000000)
    branch_limit: int | None = Field(None, ge=1, le=1000)
    ai_limit: int | None = Field(None, ge=0, le=10000000)


class ConnectionInput(Input):
    clinic_name: str = Field(min_length=2, max_length=160)
    name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=10, max_length=30)
    email: str = Field(default='', max_length=254)
    consent: Literal[True]
    _phone = field_validator('phone')(validate_phone)


class ConsentInput(Input):
    notifications_enabled: bool | None = None
    marketing_enabled: bool | None = None


class DeletePatientInput(Input):
    confirmation: Literal['DELETE MY DATA']
