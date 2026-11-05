from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, utcnow, uid


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenantRecord(Record):
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), index=True)


class Tenant(Record, Base):
    __tablename__ = 'tenants'
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(30), default='active')
    timezone: Mapped[str] = mapped_column(String(64), default='Europe/Moscow')
    description: Mapped[str] = mapped_column(Text, default='')
    phone: Mapped[str] = mapped_column(String(30), default='')
    brand_color: Mapped[str] = mapped_column(String(7), default='#0D9488')
    logo_url: Mapped[str] = mapped_column(String(500), default='')
    custom_domain: Mapped[str | None] = mapped_column(String(253), unique=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class Branch(TenantRecord, Base):
    __tablename__ = 'branches'
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(500), default='')
    phone: Mapped[str] = mapped_column(String(30), default='')
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Doctor(TenantRecord, Base):
    __tablename__ = 'doctors'
    branch_id: Mapped[str] = mapped_column(ForeignKey('branches.id'))
    name: Mapped[str] = mapped_column(String(160))
    specialty: Mapped[str] = mapped_column(String(160), default='Стоматолог')
    color: Mapped[str] = mapped_column(String(7), default='#0D9488')
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(TenantRecord, Base):
    __tablename__ = 'services'
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100), default='Стоматология')
    description: Mapped[str] = mapped_column(Text, default='')
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    price_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint('duration_minutes > 0 AND duration_minutes <= 480'), CheckConstraint('price_kopecks >= 0'))


class DoctorService(TenantRecord, Base):
    __tablename__ = 'doctor_services'
    doctor_id: Mapped[str] = mapped_column(ForeignKey('doctors.id', ondelete='CASCADE'))
    service_id: Mapped[str] = mapped_column(ForeignKey('services.id', ondelete='CASCADE'))
    __table_args__ = (UniqueConstraint('tenant_id', 'doctor_id', 'service_id'),)


class Schedule(TenantRecord, Base):
    __tablename__ = 'schedules'
    doctor_id: Mapped[str] = mapped_column(ForeignKey('doctors.id', ondelete='CASCADE'))
    branch_id: Mapped[str] = mapped_column(ForeignKey('branches.id'))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[str] = mapped_column(String(5), default='09:00')
    end_time: Mapped[str] = mapped_column(String(5), default='18:00')
    break_start: Mapped[str | None] = mapped_column(String(5), nullable=True, default='13:00')
    break_end: Mapped[str | None] = mapped_column(String(5), nullable=True, default='14:00')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('tenant_id', 'doctor_id', 'weekday'), CheckConstraint('weekday >= 0 AND weekday <= 6'))


class Patient(TenantRecord, Base):
    __tablename__ = 'patients'
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(30), default='')
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    segment: Mapped[str] = mapped_column(String(40), default='Новый пациент')
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index('ix_patients_tenant_phone', 'tenant_id', 'phone'),)


class User(Record, Base):
    __tablename__ = 'users'
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(40), default='administrator')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    doctor_id: Mapped[str | None] = mapped_column(ForeignKey('doctors.id'), nullable=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)


class AuthSession(Record, Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), default='auth')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VisitorPatient(TenantRecord, Base):
    __tablename__ = 'visitor_patients'
    session_id: Mapped[str] = mapped_column(ForeignKey('auth_sessions.id', ondelete='CASCADE'), index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id', ondelete='CASCADE'))
    __table_args__ = (UniqueConstraint('tenant_id', 'session_id'),)


class Appointment(TenantRecord, Base):
    __tablename__ = 'appointments'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'))
    doctor_id: Mapped[str] = mapped_column(ForeignKey('doctors.id'), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey('services.id'))
    branch_id: Mapped[str] = mapped_column(ForeignKey('branches.id'))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default='scheduled')
    price_kopecks: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(24), default='web')
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    __table_args__ = (UniqueConstraint('tenant_id', 'idempotency_key'), CheckConstraint('end_at > start_at'), CheckConstraint('price_kopecks >= 0'), Index('ix_appointment_tenant_start', 'tenant_id', 'start_at'))


class Lead(TenantRecord, Base):
    __tablename__ = 'leads'
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default='Новое обращение')
    stage: Mapped[str] = mapped_column(String(40), default='Новое обращение')
    source: Mapped[str] = mapped_column(String(30), default='web')
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default='')
    amount_kopecks: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint('tenant_id', 'patient_id'), UniqueConstraint('tenant_id', 'conversation_id'))


class Conversation(TenantRecord, Base):
    __tablename__ = 'conversations'
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    session_id: Mapped[str | None] = mapped_column(ForeignKey('auth_sessions.id', ondelete='CASCADE'), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default='web')
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default='ai')
    status: Mapped[str] = mapped_column(String(30), default='open')
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint('tenant_id', 'channel', 'session_id'), UniqueConstraint('tenant_id', 'channel', 'external_id'))


class Message(TenantRecord, Base):
    __tablename__ = 'messages'
    conversation_id: Mapped[str] = mapped_column(ForeignKey('conversations.id', ondelete='CASCADE'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)


class Task(TenantRecord, Base):
    __tablename__ = 'tasks'
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(20), default='open')
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    dedup_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    __table_args__ = (UniqueConstraint('tenant_id', 'dedup_key'),)


class Notification(TenantRecord, Base):
    __tablename__ = 'notifications'
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    appointment_id: Mapped[str | None] = mapped_column(ForeignKey('appointments.id'), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text, default='')
    channel: Mapped[str] = mapped_column(String(20), default='in_app')
    status: Mapped[str] = mapped_column(String(30), default='pending')
    dedup_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint('tenant_id', 'dedup_key'),)


class AutomationRule(TenantRecord, Base):
    __tablename__ = 'automation_rules'
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=120)


class Integration(TenantRecord, Base):
    __tablename__ = 'integrations'
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default='not_connected')
    description: Mapped[str] = mapped_column(Text, default='')
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AISettings(TenantRecord, Base):
    __tablename__ = 'ai_settings'
    provider: Mapped[str] = mapped_column(String(30), default='demo')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    greeting: Mapped[str] = mapped_column(String(1000), default='Здравствуйте! Помогу выбрать услугу и время приёма.')
    clinic_knowledge: Mapped[str] = mapped_column(Text, default='')
    handoff_medical: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('tenant_id'),)


class AIUsage(TenantRecord, Base):
    __tablename__ = 'ai_usage'
    provider: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(TenantRecord, Base):
    __tablename__ = 'audit_logs'
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36), default='')
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ConsentRecord(TenantRecord, Base):
    __tablename__ = 'consent_records'
    patient_id: Mapped[str] = mapped_column(ForeignKey('patients.id'))
    purpose: Mapped[str] = mapped_column(String(40))
    granted: Mapped[bool] = mapped_column(Boolean)
    version: Mapped[str] = mapped_column(String(30), default='2026-11-05')
    source: Mapped[str] = mapped_column(String(30), default='web')


class Plan(Record, Base):
    __tablename__ = 'plans'
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    price_kopecks: Mapped[int] = mapped_column(Integer)
    branch_limit: Mapped[int] = mapped_column(Integer, default=1)
    ai_limit: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (CheckConstraint('price_kopecks >= 0'),)


class Subscription(TenantRecord, Base):
    __tablename__ = 'subscriptions'
    plan_code: Mapped[str] = mapped_column(ForeignKey('plans.code'), default='BUSINESS')
    status: Mapped[str] = mapped_column(String(30), default='demo')
    payment_mode: Mapped[str] = mapped_column(String(10), default='DEMO')
    __table_args__ = (UniqueConstraint('tenant_id'),)


class ConnectionRequest(Record, Base):
    __tablename__ = 'connection_requests'
    clinic_name: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(254), default='')
    consent: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default='new')


class ChannelLink(TenantRecord, Base):
    __tablename__ = 'channel_links'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('auth_sessions.id', ondelete='CASCADE'))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey('patients.id'), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
