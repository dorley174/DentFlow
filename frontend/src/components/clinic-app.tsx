"use client";

import { useCallback, useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import {
  ArrowRight,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  HeartHandshake,
  MapPin,
  MessageCircle,
  Phone,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  X,
} from "lucide-react";
import { api, errorText, patch } from "@/lib/api";
import { Appointment, ClinicData, Config, User } from "@/lib/types";
import { currency, dateLabel, time } from "@/lib/format";
import {
  Avatar,
  Badge,
  Button,
  Empty,
  ErrorNote,
  Loading,
  Logo,
  Modal,
  Status,
  useToast,
} from "./ui";
import { BookingModal } from "./booking";
import { ChatPanel } from "./chat";
import { PatientTools } from "./patient-tools";

export function ClinicApp({ slug }: { slug: string }) {
  const [clinic, setClinic] = useState<ClinicData | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [booking, setBooking] = useState(false);
  const [chat, setChat] = useState(false);
  const [selectedService, setSelectedService] = useState("");
  const [selectedDoctor, setSelectedDoctor] = useState("");
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [cancel, setCancel] = useState<Appointment | null>(null);
  const [reschedule, setReschedule] = useState<Appointment | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [recordsError, setRecordsError] = useState("");
  const [category, setCategory] = useState("Все услуги");
  const toast = useToast();
  const refresh = useCallback(
    () =>
      api<{ appointments: Appointment[] }>(
        `/public/clinics/${encodeURIComponent(slug)}/my-appointments`,
      )
        .then((v) => {
          setAppointments(v.appointments);
          setRecordsError("");
        })
        .catch((e) => setRecordsError(errorText(e))),
    [slug],
  );
  useEffect(() => {
    api<ClinicData>(`/public/clinics/${encodeURIComponent(slug)}`)
      .then((v) => {
        setClinic(v);
        refresh();
      })
      .catch((e) => setError(errorText(e)));
    api<Config>("/public/config")
      .then(setConfig)
      .catch(() => {});
    api<{ user: User }>("/auth/me")
      .then((v) => setUser(v.user))
      .catch(() => {});
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 20000);
    return () => clearInterval(timer);
  }, [slug, refresh]);
  async function changeAppointment(
    a: Appointment,
    action: "cancel" | "confirm",
  ) {
    setActionBusy(true);
    try {
      await patch(`/public/clinics/${slug}/appointments/${a.id}`, { action });
      toast(
        action === "cancel"
          ? "Запись отменена. Время освобождено."
          : "Ваш визит подтверждён",
      );
      setCancel(null);
      await refresh();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setActionBusy(false);
    }
  }
  function openBooking(service = "", doctor = "") {
    setSelectedService(service);
    setSelectedDoctor(doctor);
    setReschedule(null);
    setBooking(true);
  }
  if (error)
    return (
      <div className="standalone-state">
        <Logo />
        <ErrorNote message={error} />
        <Link href="/" className="btn btn-secondary">
          На главную
        </Link>
      </div>
    );
  if (!clinic) return <Loading text="Загружаем сайт клиники…" />;
  const { tenant, services, doctors, branches } = clinic;
  const categories = [
    "Все услуги",
    ...Array.from(
      new Set(services.filter((s) => s.active).map((s) => s.category)),
    ),
  ];
  const canAdmin =
    user && ["owner", "manager", "administrator", "doctor"].includes(user.role);
  return (
    <main
      className="clinic-page"
      style={
        { "--clinic-color": tenant.brand_color || "#087f8c" } as CSSProperties
      }
    >
      {config?.dev_tools && (
        <div className="dev-ribbon">
          <span>
            <i />
            Тестовая клиника · используйте вымышленные данные
          </span>
          {canAdmin && (
            <Link href="/admin">
              Кабинет администратора <ArrowRight size={14} />
            </Link>
          )}
          {user?.role === "super_admin" && (
            <Link href="/super">
              Управление платформой <ArrowRight size={14} />
            </Link>
          )}
        </div>
      )}
      <header className="clinic-nav page-container">
        <Link href={`/clinic/${slug}`} className="clinic-brand">
          <span className="clinic-brand-symbol">
            {typeof tenant.logo_url === "string" &&
            tenant.logo_url &&
            (tenant.logo_url.startsWith("https://") ||
              tenant.logo_url.startsWith("/")) ? (
              <img
                src={tenant.logo_url}
                alt=""
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <Sparkles size={25} />
            )}
          </span>
          <span>
            {tenant.name}
            <small>стоматология с заботой о вас</small>
          </span>
        </Link>
        <nav>
          <a href="#services">Услуги и цены</a>
          <a href="#doctors">Врачи</a>
          <a href="#branches">Клиники</a>
          <a href="#my-appointments">Мои записи</a>
        </nav>
        <Button onClick={() => openBooking()}>
          Записаться <ArrowRight size={16} />
        </Button>
      </header>
      <section className="clinic-hero page-container">
        <div className="clinic-hero-copy">
          <Badge tone="green" dot>
            Забота начинается с первого визита
          </Badge>
          <h1>
            Больше поводов
            <br />
            для вашей <em>улыбки.</em>
          </h1>
          <p>
            {tenant.description ||
              "Выберите удобное время, познакомьтесь с врачом и запишитесь онлайн. Мы поможем сделать первый шаг."}
          </p>
          <div className="hero-actions">
            <Button onClick={() => openBooking()}>
              Выбрать время <ArrowRight size={18} />
            </Button>
            <Button variant="secondary" onClick={() => setChat(true)}>
              <MessageCircle size={18} />
              Задать вопрос
            </Button>
          </div>
          <div className="clinic-hero-points">
            <span>
              <Check size={15} />
              Актуальное расписание
            </span>
            <span>
              <Check size={15} />
              Цены до записи
            </span>
            <span>
              <Check size={15} />
              Удобный перенос
            </span>
          </div>
        </div>
        <div className="clinic-hero-art" aria-hidden="true">
          <div className="clinic-orbit orbit-one" />
          <div className="clinic-orbit orbit-two" />
          <div className="tooth-sculpture">
            <svg viewBox="0 0 240 300">
              <defs>
                <linearGradient id="tooth-shade" x1="0" x2="1" y1="0" y2="1">
                  <stop offset="0" stopColor="white" />
                  <stop offset="1" stopColor="#d4eee7" />
                </linearGradient>
              </defs>
              <path
                d="M54 39C18 53 27 112 43 147c18 38 10 95 36 108 25 13 19-67 41-66 25 0 20 81 46 65 25-14 18-70 36-108 17-37 23-94-12-108-27-11-43 11-69 11S81 27 54 39Z"
                fill="url(#tooth-shade)"
              />
              <path
                d="M74 61c18-4 29 10 49 10s35-13 48-9"
                fill="none"
                stroke="#d4eee7"
                strokeWidth="8"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <div className="floating-care">
            <span>
              <HeartHandshake size={22} />
            </span>
            <div>
              <strong>В вашем ритме</strong>
              <small>Запись онлайн, в любое время</small>
            </div>
          </div>
          <div className="floating-time">
            <CalendarDays size={18} />
            <span>Ваш визит — под контролем</span>
            <Check size={15} />
          </div>
        </div>
      </section>
      <section id="services" className="page-container clinic-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">ПОНЯТНО С ПЕРВОГО ШАГА</span>
            <h2>Услуги и стоимость</h2>
          </div>
          <p>
            Выберите услугу, чтобы увидеть
            <br />
            подходящих врачей и свободные окна.
          </p>
        </div>
        <div className="filter-pills">
          {categories.map((c) => (
            <button
              className={category === c ? "active" : ""}
              key={c}
              onClick={() => setCategory(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <div className="service-grid">
          {services
            .filter(
              (s) =>
                s.active &&
                (category === "Все услуги" || s.category === category),
            )
            .map((s, i) => (
              <button
                className="service-card"
                key={s.id}
                onClick={() => openBooking(s.id)}
              >
                <span className="service-number">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span>
                  <small>{s.category}</small>
                  <strong>{s.name}</strong>
                  <span className="service-duration">
                    <Clock3 size={14} />
                    {s.duration_minutes} мин.
                  </span>
                </span>
                <span className="service-price">
                  {currency(s.price_kopecks)}
                  <ArrowRight size={18} />
                </span>
              </button>
            ))}
        </div>
      </section>
      <section id="doctors" className="clinic-doctors-section">
        <div className="page-container clinic-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">ПОЗНАКОМИМСЯ БЛИЖЕ</span>
              <h2>Врачи вашей клиники</h2>
            </div>
            <p>
              Выберите специалиста
              <br />и удобное время приёма.
            </p>
          </div>
          <div className="doctor-grid">
            {doctors
              .filter((d) => d.active)
              .map((d, i) => (
                <article className="doctor-card" key={d.id}>
                  <div className={`doctor-portrait doctor-tone-${i % 4}`}>
                    <Avatar name={d.name} color={d.color} />
                    <Stethoscope size={30} />
                  </div>
                  <div className="doctor-card-info">
                    <span>{d.specialty}</span>
                    <h3>{d.name}</h3>
                    <p>
                      <MapPin size={14} />
                      {branches.find((b) => b.id === d.branch_id)?.name}
                    </p>
                    <button
                      onClick={() =>
                        openBooking(d.service_ids?.[0] || "", d.id)
                      }
                    >
                      Выбрать время <ArrowRight size={17} />
                    </button>
                  </div>
                </article>
              ))}
          </div>
        </div>
      </section>
      <section id="my-appointments" className="page-container clinic-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">ВСЁ ПОД РУКОЙ</span>
            <h2>Мои записи</h2>
          </div>
          <Button variant="secondary" onClick={() => refresh()}>
            Обновить записи
          </Button>
        </div>
        <p className="section-description">
          Здесь отображаются записи, созданные в этом браузере. Сохраните доступ
          к браузеру, чтобы перенести или отменить визит.
        </p>
        <ErrorNote message={recordsError} />
        {!appointments.length ? (
          <div className="patient-empty">
            <CalendarDays size={28} />
            <div>
              <h3>Ваш первый визит ещё впереди</h3>
              <p>Выберите услугу и время — запись появится здесь.</p>
            </div>
            <Button variant="secondary" onClick={() => openBooking()}>
              Записаться
            </Button>
          </div>
        ) : (
          <div className="patient-appointments">
            {appointments.map((a) => (
              <article key={a.id} className="patient-appointment">
                <div className="visit-date">
                  <strong>
                    {dateLabel(a.start_at, {
                      day: "numeric",
                      month: undefined,
                    })}
                  </strong>
                  <span>
                    {dateLabel(a.start_at, { day: undefined, month: "short" })}
                  </span>
                </div>
                <div className="visit-details">
                  <h3>{a.service_name}</h3>
                  <p>
                    {time(a.start_at)} · {a.doctor_name}
                  </p>
                  <small>{a.branch_name}</small>
                </div>
                <Status value={a.status} />
                {!["cancelled", "completed", "no_show"].includes(a.status) && (
                  <div className="visit-actions">
                    {a.status === "scheduled" && (
                      <Button
                        variant="secondary"
                        loading={actionBusy}
                        onClick={() => changeAppointment(a, "confirm")}
                      >
                        Подтвердить
                      </Button>
                    )}
                    <button
                      className="text-btn"
                      onClick={() => {
                        setReschedule(a);
                        setBooking(true);
                      }}
                    >
                      Перенести
                    </button>
                    <button
                      className="text-btn danger-text"
                      onClick={() => setCancel(a)}
                    >
                      Отменить
                    </button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
        {appointments.length > 0 && (
          <PatientTools
            slug={slug}
            version={appointments
              .map((a) => `${a.id}:${a.status}:${a.start_at}`)
              .join("|")}
          />
        )}
      </section>
      <section id="branches" className="page-container clinic-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">РЯДОМ С ВАМИ</span>
            <h2>Адреса и контакты</h2>
          </div>
        </div>
        <div className="branch-grid">
          {branches.map((b) => (
            <article key={b.id} className="branch-card">
              <span className="branch-icon">
                <MapPin size={25} />
              </span>
              <div>
                <h3>{b.name}</h3>
                <p>{b.address}</p>
                {(b.phone || tenant.phone) && (
                  <a
                    className="contact-phone"
                    href={`tel:${String(b.phone || tenant.phone).replace(/[^+0-9]/g, "")}`}
                  >
                    <Phone size={16} />
                    {b.phone || tenant.phone}
                  </a>
                )}
              </div>
              <Button variant="secondary" onClick={() => openBooking()}>
                Записаться <ChevronRight size={16} />
              </Button>
            </article>
          ))}
        </div>
      </section>
      <footer className="clinic-footer page-container">
        <span>{tenant.name} · Онлайн-запись</span>
        <Link href="/privacy">Обработка персональных данных</Link>
        <Link href="/" className="powered-by">
          Работает на <Logo />
        </Link>
      </footer>
      <button
        className="chat-launcher"
        aria-label="Открыть чат с клиникой"
        onClick={() => setChat(!chat)}
      >
        {chat ? <X size={24} /> : <MessageCircle size={25} />}
        <span>{chat ? "Закрыть" : "Поможем с записью"}</span>
      </button>
      {chat && (
        <aside className="floating-chat" aria-label="Чат с клиникой">
          <ChatPanel slug={slug} />
        </aside>
      )}
      {booking && (
        <BookingModal
          open
          onClose={() => setBooking(false)}
          clinic={clinic}
          appointment={reschedule}
          initialService={selectedService}
          initialDoctor={selectedDoctor}
          onCreated={refresh}
        />
      )}
      <Modal
        open={Boolean(cancel)}
        title="Отменить этот визит?"
        onClose={() => setCancel(null)}
      >
        <p>
          Запись на {cancel && dateLabel(cancel.start_at)} в{" "}
          {cancel && time(cancel.start_at)} будет отменена, а время станет
          доступно другим пациентам.
        </p>
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setCancel(null)}>
            Сохранить запись
          </Button>
          <Button
            variant="danger"
            loading={actionBusy}
            onClick={() => cancel && changeAppointment(cancel, "cancel")}
          >
            Отменить визит
          </Button>
        </div>
      </Modal>
    </main>
  );
}
