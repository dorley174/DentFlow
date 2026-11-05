"""MIS contract. The included adapter operates on DentFlow's own PostgreSQL.

No claims of live 1C/IDENT/Infodent connectivity; no external URLs or tokens here.
New adapters must preserve tenant scoping, availability checks and idempotency.
"""
from typing import Protocol
from sqlalchemy import select
from .. import models as m
from ..services.common import serial, tenant_item
from ..services.booking import available_slots, create_appointment, change_appointment

class MISAdapter(Protocol):
    def get_doctors(self) -> list[dict]: ...
    def get_services(self) -> list[dict]: ...
    def get_schedule(self) -> list[dict]: ...
    def get_available_slots(self, service_id, day, doctor_id=None, branch_id=None) -> list[dict]: ...
    def create_appointment(self, patient_id, service_id, doctor_id, branch_id, start_at, idempotency_key, identity_id): ...
    def update_appointment(self, appointment_id, start_at): ...
    def cancel_appointment(self, appointment_id): ...
    def get_appointments(self) -> list[dict]: ...

class MockMISAdapter:
    """A functional database-backed test MIS, not a static fixture response."""
    name = 'DentFlow Internal / MockMIS'
    def __init__(self, db, tenant):
        self.db, self.tenant = db, tenant

    def _rows(self, model):
        return [serial(x, self.db) for x in self.db.scalars(select(model).where(model.tenant_id == self.tenant.id))]

    def get_doctors(self): return self._rows(m.Doctor)
    def get_services(self): return self._rows(m.Service)
    def get_schedule(self): return self._rows(m.Schedule)
    def get_appointments(self): return self._rows(m.Appointment)

    def get_available_slots(self, service_id, day, doctor_id=None, branch_id=None):
        return available_slots(self.db, self.tenant, service_id, day, doctor_id, branch_id)

    def create_appointment(self, patient_id, service_id, doctor_id, branch_id, start_at, idempotency_key, identity_id):
        patient = tenant_item(self.db, m.Patient, patient_id, self.tenant.id)
        return create_appointment(self.db, self.tenant, patient, service_id, doctor_id, branch_id,
                                  start_at, idempotency_key, identity_id, source='mis_mock')

    def update_appointment(self, appointment_id, start_at):
        appointment = tenant_item(self.db, m.Appointment, appointment_id, self.tenant.id)
        return change_appointment(self.db, self.tenant, appointment, action='reschedule', start_at=start_at)

    def cancel_appointment(self, appointment_id):
        appointment = tenant_item(self.db, m.Appointment, appointment_id, self.tenant.id)
        return change_appointment(self.db, self.tenant, appointment, action='cancel')
