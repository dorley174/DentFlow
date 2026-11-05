"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock3,
  MapPin,
  UserRound,
} from "lucide-react";
import { api, errorText, patch, post } from "@/lib/api";
import { Appointment, ClinicData, Patient, Slot } from "@/lib/types";
import { addDays, currency, dateLabel, dayKey, time } from "@/lib/format";
import {
  Avatar,
  Badge,
  Button,
  Empty,
  ErrorNote,
  Field,
  Loading,
  Modal,
} from "./ui";

type Props = {
  open: boolean;
  onClose: () => void;
  clinic: ClinicData;
  patients?: Patient[];
  onCreated?: () => void;
  admin?: boolean;
  appointment?: Appointment | null;
  initialService?: string;
  initialDoctor?: string;
};
export function BookingModal(props: Props) {
  return (
    <Modal
      open={props.open}
      onClose={props.onClose}
      title={props.appointment ? "Перенести запись" : "Записаться на приём"}
      description={`${props.clinic.tenant.name} · время по Москве`}
      wide
    >
      <BookingWizard {...props} />
    </Modal>
  );
}

function BookingWizard({
  onClose,
  clinic,
  patients = [],
  onCreated,
  admin = false,
  appointment,
  initialService,
  initialDoctor,
}: Props) {
  const [step, setStep] = useState(appointment ? 1 : 0);
  const [serviceId, setServiceId] = useState(
    appointment?.service_id ||
      initialService ||
      clinic.services.find((s) => s.active)?.id ||
      "",
  );
  const firstDoctor = clinic.doctors.find((d) => d.id === initialDoctor);
  const [branchId, setBranchId] = useState(
    appointment?.branch_id ||
      firstDoctor?.branch_id ||
      clinic.branches[0]?.id ||
      "",
  );
  const [doctorId, setDoctorId] = useState(
    appointment?.doctor_id || initialDoctor || "",
  );
  const [date, setDate] = useState(addDays(dayKey(), 1));
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState(appointment?.patient_name || "");
  const [phone, setPhone] = useState("");
  const [patientId, setPatientId] = useState("");
  const [consent, setConsent] = useState(false);
  const [notifications, setNotifications] = useState(false);
  const [result, setResult] = useState<Appointment | null>(null);
  const requestId = useRef(
    crypto.randomUUID
      ? crypto.randomUUID()
      : Array.from(crypto.getRandomValues(new Uint8Array(16)))
          .map((v) => v.toString(16).padStart(2, "0"))
          .join(""),
  );
  const service = clinic.services.find((s) => s.id === serviceId);
  const doctors = clinic.doctors.filter(
    (d) =>
      d.active &&
      d.branch_id === branchId &&
      d.service_ids?.includes(serviceId),
  );
  useEffect(() => {
    if (!appointment && !doctors.some((d) => d.id === doctorId))
      setDoctorId(doctors[0]?.id || "");
  }, [branchId, serviceId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (step !== 1 || !serviceId || !doctorId || !date) return;
    let active = true;
    setLoading(true);
    setError("");
    setSlot(null);
    const query = new URLSearchParams({
      service_id: serviceId,
      doctor_id: doctorId,
      branch_id: branchId,
      date,
    });
    api<{ slots: Slot[] }>(
      `/public/clinics/${encodeURIComponent(clinic.tenant.slug)}/slots?${query}`,
    )
      .then((v) => active && setSlots(v.slots))
      .catch((e) => active && setError(errorText(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [step, serviceId, doctorId, branchId, date, clinic.tenant.slug]);
  async function submit() {
    if (!slot || !service) return;
    setBusy(true);
    setError("");
    try {
      let response: { appointment?: Appointment } | Appointment;
      // Rescheduling and creation always go through the same transactional backend.
      if (appointment) {
        response = await patch<{ appointment?: Appointment } | Appointment>(
          admin
            ? `/admin/appointments/${appointment.id}`
            : `/public/clinics/${clinic.tenant.slug}/appointments/${appointment.id}`,
          { action: "reschedule", start_at: slot.start_at },
        );
      } else {
        response = await post<{ appointment?: Appointment } | Appointment>(
          admin
            ? "/admin/appointments"
            : `/public/clinics/${clinic.tenant.slug}/appointments`,
          {
            service_id: serviceId,
            doctor_id: slot.doctor_id,
            branch_id: branchId,
            start_at: slot.start_at,
            ...(admin && patientId
              ? { patient_id: patientId }
              : {
                  patient_name: name.trim(),
                  phone: phone.trim(),
                  consent_pd: consent,
                  consent_notifications: notifications,
                }),
            idempotency_key: requestId.current,
          },
        );
      }
      const saved = (
        "appointment" in response && response.appointment
          ? response.appointment
          : response
      ) as Appointment;
      setResult(saved);
      setStep(3);
      onCreated?.();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  if (step === 3 && result)
    return (
      <div className="booking-success">
        <span>
          <CheckCircle2 size={37} />
        </span>
        <Badge tone="green">Запись сохранена</Badge>
        <h2>
          {appointment ? "Время приёма изменено" : "Будем рады вас видеть"}
        </h2>
        <p>{result.service_name || service?.name}</p>
        <div className="confirmation-card">
          <div>
            <CalendarDays size={19} />
            <strong>
              {dateLabel(result.start_at || slot!.start_at, {
                weekday: "long",
              })}
              , {time(result.start_at || slot!.start_at)}
            </strong>
          </div>
          <div>
            <UserRound size={19} />
            {result.doctor_name ||
              clinic.doctors.find((d) => d.id === slot?.doctor_id)?.name}
          </div>
          <div>
            <MapPin size={19} />
            {clinic.branches.find((b) => b.id === branchId)?.address}
          </div>
        </div>
        <p className="muted">
          {admin
            ? "Запись доступна в календаре и карточке пациента."
            : "Проверить или изменить приём можно в разделе «Мои записи» в этом браузере."}
        </p>
        <Button onClick={onClose}>
          Готово <Check size={17} />
        </Button>
      </div>
    );
  return (
    <div className="booking-wizard">
      <div className="step-track">
        {["Услуга и врач", "Дата и время", "Подтверждение"].map((label, i) => (
          <div key={label} className={i <= step ? "current" : ""}>
            <span>{i < step ? <Check size={14} /> : i + 1}</span>
            <small>{label}</small>
          </div>
        ))}
      </div>
      {step === 0 && (
        <div className="booking-stage">
          <Field label="Выберите филиал">
            <select
              value={branchId}
              onChange={(e) => setBranchId(e.target.value)}
            >
              {clinic.branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} · {b.address}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Услуга">
            <select
              value={serviceId}
              onChange={(e) => setServiceId(e.target.value)}
            >
              {clinic.services
                .filter((s) => s.active)
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} — {currency(s.price_kopecks)}
                  </option>
                ))}
            </select>
          </Field>
          {service && (
            <div className="inline-note">
              <Clock3 size={16} />
              {service.duration_minutes} минут
              <span>Стоимость: {currency(service.price_kopecks)}</span>
            </div>
          )}
          <div className="field">
            <span>Врач</span>
            <div className="doctor-picker">
              {doctors.map((d) => (
                <button
                  type="button"
                  key={d.id}
                  className={doctorId === d.id ? "selected" : ""}
                  onClick={() => setDoctorId(d.id)}
                >
                  <Avatar name={d.name} color={d.color} />
                  <span>
                    <strong>{d.name}</strong>
                    <small>{d.specialty}</small>
                  </span>
                  <span className="radio-mark">
                    {doctorId === d.id && <Check size={12} />}
                  </span>
                </button>
              ))}
            </div>
            {!doctors.length && (
              <Empty
                title="Нет доступных врачей"
                text="Выберите другую услугу или филиал."
              />
            )}
          </div>
        </div>
      )}
      {step === 1 && (
        <div className="booking-stage">
          <div className="booking-summary">
            <strong>{service?.name}</strong>
            <span>
              {clinic.doctors.find((d) => d.id === doctorId)?.name} ·{" "}
              {service?.duration_minutes} мин.
            </span>
          </div>
          <Field label="Дата приёма">
            <input
              type="date"
              value={date}
              min={dayKey()}
              max={addDays(dayKey(), 90)}
              onChange={(e) => setDate(e.target.value)}
            />
          </Field>
          <div className="quick-dates">
            {[0, 1, 2, 3, 4, 5].map((n) => {
              const d = addDays(dayKey(), n);
              return (
                <button
                  key={d}
                  className={date === d ? "selected" : ""}
                  onClick={() => setDate(d)}
                >
                  {n === 0
                    ? "Сегодня"
                    : n === 1
                      ? "Завтра"
                      : dateLabel(d, { month: "short" })}
                </button>
              );
            })}
          </div>
          <div className="field">
            <span>
              Свободное время <small>МСК</small>
            </span>
            {loading ? (
              <Loading text="Проверяем расписание…" />
            ) : slots.length ? (
              <div className="slot-grid">
                {slots.map((s) => (
                  <button
                    key={`${s.doctor_id}-${s.start_at}`}
                    className={slot?.start_at === s.start_at ? "selected" : ""}
                    onClick={() => setSlot(s)}
                  >
                    {time(s.start_at)}
                  </button>
                ))}
              </div>
            ) : (
              <Empty
                title="На этот день свободных окон нет"
                text="Попробуйте соседнюю дату или другого врача."
              />
            )}
          </div>
        </div>
      )}
      {step === 2 && (
        <form
          id="booking-submit"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="booking-stage"
        >
          <div className="booking-review">
            <span className="review-icon">
              <CalendarDays size={25} />
            </span>
            <div>
              <strong>
                {dateLabel(slot!.start_at, { weekday: "long" })} в{" "}
                {time(slot!.start_at)}
              </strong>
              <span>
                {service?.name} · {currency(service?.price_kopecks)}
              </span>
              <small>
                {clinic.doctors.find((d) => d.id === doctorId)?.name}
              </small>
            </div>
          </div>
          {!appointment && (
            <>
              {admin && (
                <Field label="Пациент">
                  <select
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                  >
                    <option value="">Новый пациент</option>
                    {patients.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.phone}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {!patientId && (
                <>
                  <div className="form-grid">
                    <Field label="Ваше имя">
                      <input
                        required
                        minLength={2}
                        maxLength={100}
                        autoComplete="name"
                        placeholder="Как к вам обращаться"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                      />
                    </Field>
                    <Field label="Телефон">
                      <input
                        required
                        type="tel"
                        autoComplete="tel"
                        placeholder="+7 (999) 123-45-67"
                        minLength={10}
                        maxLength={30}
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                      />
                    </Field>
                  </div>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      required
                      checked={consent}
                      onChange={(e) => setConsent(e.target.checked)}
                    />
                    <span>
                      Согласен на обработку имени и телефона для организации
                      записи.{" "}
                      <a href="/privacy" target="_blank" rel="noreferrer">
                        Условия обработки данных
                      </a>
                    </span>
                  </label>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={notifications}
                      onChange={(e) => setNotifications(e.target.checked)}
                    />
                    <span>
                      Хочу получать уведомления о записи и напоминания. Можно
                      отключить позднее.
                    </span>
                  </label>
                </>
              )}
            </>
          )}
          <div className="inline-note">
            {appointment
              ? "Старое время освободится после успешного переноса."
              : "Данные сохранятся после подтверждения. Оплата сейчас не требуется."}
          </div>
        </form>
      )}
      <ErrorNote message={error} />
      <div className="modal-actions">
        {step > (appointment ? 1 : 0) ? (
          <Button
            variant="secondary"
            onClick={() => {
              setError("");
              setStep(step - 1);
            }}
          >
            <ArrowLeft size={16} />
            Назад
          </Button>
        ) : (
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
        )}
        {step < 2 ? (
          <Button
            onClick={() => setStep(step + 1)}
            disabled={step === 0 ? !doctorId || !serviceId || !branchId : !slot}
          >
            Продолжить
            <ArrowRight size={16} />
          </Button>
        ) : (
          <Button type="submit" form="booking-submit" loading={busy}>
            {appointment ? "Перенести запись" : "Подтвердить запись"}
            <Check size={16} />
          </Button>
        )}
      </div>
    </div>
  );
}
