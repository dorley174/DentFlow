"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bell,
  Bot,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Download,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  MessageCircle,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Stethoscope,
  TrendingUp,
  UserRound,
  UsersRound,
  Waypoints,
  X,
  Zap,
  Building2,
  CreditCard,
  List,
} from "lucide-react";
import { api, ApiError, errorText, patch, post } from "@/lib/api";
import {
  Appointment,
  Bootstrap,
  Config,
  Patient,
  Row,
  User,
} from "@/lib/types";
import {
  addDays,
  currency,
  dateLabel,
  dayKey,
  roles,
  shortNumber,
  statuses,
  time,
} from "@/lib/format";
import {
  Avatar,
  Badge,
  Button,
  Empty,
  ErrorNote,
  Field,
  Loading,
  Logo,
  Modal,
  Status,
  useToast,
} from "./ui";
import { BookingModal } from "./booking";
import { AppointmentTable, Calendar } from "./calendar";
import { CRM } from "./crm";
import { Conversations } from "./conversations";
import { FormField, ResourceManager } from "./resource-manager";
import {
  AISettings,
  Automations,
  ClinicSettings,
  Integrations,
} from "./admin-settings";

const navItems = [
  { id: "overview", label: "Обзор", icon: LayoutDashboard },
  { id: "calendar", label: "Расписание", icon: CalendarDays },
  { id: "appointments", label: "Записи", icon: List },
  { id: "patients", label: "Пациенты", icon: UsersRound },
  { id: "crm", label: "CRM", icon: GitBranch },
  { id: "conversations", label: "Диалоги", icon: MessageCircle },
  { id: "tasks", label: "Задачи", icon: ListChecks },
  { id: "doctors", label: "Врачи", icon: Stethoscope },
  { id: "services", label: "Услуги", icon: CreditCard },
  { id: "branches", label: "Филиалы", icon: Building2 },
  { id: "automations", label: "Автоматизации", icon: Zap },
  { id: "ai", label: "AI-администратор", icon: Sparkles },
  { id: "analytics", label: "Аналитика", icon: TrendingUp },
  { id: "integrations", label: "Интеграции", icon: Waypoints },
  { id: "employees", label: "Сотрудники", icon: UserRound },
  { id: "settings", label: "Настройки", icon: Settings },
];
const auditNames: Record<string, string> = {
  "appointment.created": "Создана запись",
  "appointment.rescheduled": "Запись перенесена",
  "appointment.cancelled": "Запись отменена",
  "appointment.updated": "Запись обновлена",
  "appointment.status_changed": "Статус записи изменён",
  "conversation.handoff": "Диалог передан сотруднику",
  "automations.run": "Выполнены автоматизации",
  "demo.seeded": "Загружены учебные данные",
  "settings.updated": "Настройки сохранены",
  "dashboard.read": "Открыт обзор клиники",
  "conversation.read": "Просмотрен диалог",
  "conversation.mode_changed": "Изменён режим диалога",
  "conversation.staff_replied": "Отправлен ответ сотрудника",
  "records.read": "Просмотрены данные",
  "doctors.created": "Добавлен врач",
  "doctors.updated": "Обновлены данные врача",
  "services.created": "Добавлена услуга",
  "services.updated": "Обновлён прайс",
  "branches.created": "Добавлен филиал",
  "branches.updated": "Обновлён филиал",
  "schedules.created": "Добавлена рабочая смена",
  "schedules.updated": "Изменены рабочие часы",
  "employees.created": "Добавлен сотрудник",
  "employees.updated": "Обновлён доступ сотрудника",
  "tasks.created": "Создана задача",
  "tasks.updated": "Обновлена задача",
  "leads.created": "Создано обращение",
  "leads.updated": "Обновлена стадия обращения",
  "consent.updated": "Обновлены согласия пациента",
  "patient.exported": "Выгружены данные пациента",
  "patient.erasure_requested": "Запрошено удаление данных",
  "auth.login": "Вход сотрудника",
  "task.created": "Создана задача",
  "lead.created": "Новое обращение",
};

function MetricCards({ data }: { data: Bootstrap }) {
  const m = data.metrics || {};
  const items = [
    {
      label: "Записей сегодня",
      value: shortNumber(m.appointments_today || 0),
      note: "По расписанию клиники",
      icon: CalendarDays,
      color: "teal",
    },
    {
      label: "Пациентов в базе",
      value: shortNumber(m.active_patients || data.patients.length),
      note: "В вашем рабочем пространстве",
      icon: UsersRound,
      color: "blue",
    },
    {
      label: "Новых обращений",
      value: shortNumber(m.new_leads || 0),
      note: "Начало воронки CRM",
      icon: MessageCircle,
      color: "purple",
    },
    {
      label: "Ожидаемая сумма",
      value: currency(m.expected_revenue_kopecks || 0),
      note: "Стоимость активных записей",
      icon: TrendingUp,
      color: "amber",
    },
  ];
  return (
    <div className="metric-grid">
      {items.map((i) => (
        <article className="metric-card" key={i.label}>
          <div>
            <span>{i.label}</span>
            <span className={`metric-icon ${i.color}`}>
              <i.icon size={18} />
            </span>
          </div>
          <strong>{i.value}</strong>
          <small>{i.note}</small>
        </article>
      ))}
    </div>
  );
}

function ActivityChart({ appointments }: { appointments: Appointment[] }) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(dayKey(), i - 3));
  const values = days.map(
    (d) =>
      appointments.filter(
        (a) => dayKey(a.start_at) === d && a.status !== "cancelled",
      ).length,
  );
  const max = Math.max(...values, 1);
  return (
    <div
      className="activity-chart"
      role="img"
      aria-label={`Записи за неделю: ${days.map((d, i) => `${dateLabel(d, { month: "short" })}: ${values[i]}`).join("; ")}`}
    >
      <div className="chart-grid-lines">
        <i />
        <i />
        <i />
      </div>
      {days.map((d, i) => (
        <div
          className={`chart-column ${d === dayKey() ? "current" : ""}`}
          key={d}
        >
          <span>{values[i]}</span>
          <div
            style={{ height: `${Math.max(3, (values[i] / max) * 130)}px` }}
          />
          <small>{dateLabel(d, { day: "numeric", month: "short" })}</small>
        </div>
      ))}
    </div>
  );
}

function Overview({
  data,
  onNavigate,
  onSelect,
  onSaved,
}: {
  data: Bootstrap;
  onNavigate: (s: string) => void;
  onSelect: (a: Appointment) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const today = data.appointments.filter(
    (a) => dayKey(a.start_at) === dayKey() && a.status !== "cancelled",
  );
  const tasks = data.tasks.filter((t) => t.status !== "done").slice(0, 4);
  async function complete(id: string) {
    try {
      await patch(`/admin/tasks/${id}`, { status: "done" });
      onSaved();
      toast("Задача выполнена");
    } catch (e) {
      toast(errorText(e), "error");
    }
  }
  return (
    <>
      <MetricCards data={data} />
      <div className="overview-grid">
        <div className="panel overview-schedule">
          <div className="panel-inner-heading">
            <div>
              <h3>
                Сегодня в расписании{" "}
                <span className="count-label">{today.length}</span>
              </h3>
              <p>{dateLabel(new Date(), { weekday: "long" })}</p>
            </div>
            <button className="text-btn" onClick={() => onNavigate("calendar")}>
              Открыть календарь
              <ArrowUpRight size={15} />
            </button>
          </div>
          <AppointmentTable
            appointments={today.slice(0, 6)}
            onSelect={onSelect}
          />
        </div>
        <div className="panel overview-activity">
          <div className="panel-inner-heading">
            <div>
              <h3>Ритм клиники</h3>
              <p>Записи за 7 дней</p>
            </div>
            <span className="round-icon">
              <Activity size={18} />
            </span>
          </div>
          <ActivityChart appointments={data.appointments} />
          <div className="chart-legend">
            <i />
            Активные и завершённые записи
          </div>
        </div>
      </div>
      {data.user.role !== "doctor" && (
        <div className="overview-bottom">
          <div className="panel task-preview">
            <div className="panel-inner-heading">
              <div>
                <h3>Фокус команды</h3>
                <p>Ближайшие задачи</p>
              </div>
              <button className="text-btn" onClick={() => onNavigate("tasks")}>
                Все задачи
                <ChevronRight size={16} />
              </button>
            </div>
            {tasks.length ? (
              tasks.map((t) => (
                <div className="task-line" key={t.id}>
                  <button
                    className="task-check"
                    aria-label={`Выполнить задачу: ${t.title}`}
                    onClick={() => complete(t.id)}
                  >
                    <Check size={14} />
                  </button>
                  <div>
                    <strong>{t.title}</strong>
                    <small>
                      {t.due_at
                        ? `${dateLabel(t.due_at, { month: "short" })}, ${time(t.due_at)}`
                        : "Без срока"}{" "}
                      ·{" "}
                      {data.staff.find((s) => s.id === t.assigned_to)?.name
                        ? String(
                            data.staff.find((s) => s.id === t.assigned_to)
                              ?.name,
                          )
                        : "Команда клиники"}
                    </small>
                  </div>
                  <Status value={t.status} />
                </div>
              ))
            ) : (
              <Empty
                title="Всё под контролем"
                text="Открытых задач пока нет."
              />
            )}
          </div>
          <div className="panel activity-feed">
            <div className="panel-inner-heading">
              <div>
                <h3>Последние события</h3>
                <p>Журнал действий</p>
              </div>
              <ShieldCheck size={19} />
            </div>
            {data.audit_logs.slice(0, 5).map((log) => (
              <div className="activity-line" key={log.id}>
                <span />
                <div>
                  <strong>
                    {auditNames[String(log.action)] || "Событие журнала"}
                  </strong>
                  <small>
                    {log.created_at
                      ? `${dateLabel(String(log.created_at), { month: "short" })} в ${time(String(log.created_at))}`
                      : "Событие сохранено"}
                  </small>
                </div>
              </div>
            ))}
            {!data.audit_logs.length && (
              <Empty
                title="Событий пока нет"
                text="Действия сотрудников будут отражены здесь."
              />
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Analytics({ data }: { data: Bootstrap }) {
  const m = data.metrics || {};
  const completed = data.appointments.filter((a) => a.status === "completed");
  const active = data.appointments.filter(
    (a) => !["cancelled", "no_show"].includes(a.status),
  );
  function download() {
    const report = {
      generated_at: new Date().toISOString(),
      clinic: data.tenant.name,
      metrics: data.metrics,
      statuses: Object.fromEntries(
        ["scheduled", "confirmed", "completed", "cancelled", "no_show"].map(
          (s) => [s, data.appointments.filter((a) => a.status === s).length],
        ),
      ),
      notice:
        "Суммы рассчитаны по стоимости услуг; это не бухгалтерский отчёт о полученных платежах.",
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `dentflow-analytics-${dayKey()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Аналитика клиники</h2>
          <p>Рассчитана по данным текущего рабочего пространства.</p>
        </div>
        <Button variant="secondary" onClick={download}>
          <Download size={16} />
          Скачать отчёт
        </Button>
      </div>
      <MetricCards data={data} />
      <div className="analytics-grid">
        <div className="panel analytics-chart">
          <h3>Динамика записей</h3>
          <ActivityChart appointments={data.appointments} />
        </div>
        <div className="panel status-breakdown">
          <h3>Статусы визитов</h3>
          {["scheduled", "confirmed", "completed", "cancelled", "no_show"].map(
            (s) => {
              const count = data.appointments.filter(
                (a) => a.status === s,
              ).length;
              return (
                <div key={s}>
                  <span>{statuses[s]}</span>
                  <div>
                    <i
                      style={{
                        width: `${(count / Math.max(data.appointments.length, 1)) * 100}%`,
                      }}
                    />
                  </div>
                  <strong>{count}</strong>
                </div>
              );
            },
          )}
        </div>
      </div>
      <div className="panel table-panel">
        <div className="panel-inner-heading">
          <div>
            <h3>По филиалам</h3>
            <p>Все записи, доступные в текущем кабинете</p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Филиал</th>
                <th>Врачей</th>
                <th>Активных записей</th>
                <th>Завершено</th>
                <th>Стоимость завершённых услуг</th>
              </tr>
            </thead>
            <tbody>
              {data.branches.map((b) => (
                <tr key={b.id}>
                  <td>
                    <strong>{b.name}</strong>
                    <small>{b.address}</small>
                  </td>
                  <td>
                    {data.doctors.filter((d) => d.branch_id === b.id).length}
                  </td>
                  <td>{active.filter((a) => a.branch_id === b.id).length}</td>
                  <td>
                    {completed.filter((a) => a.branch_id === b.id).length}
                  </td>
                  <td>
                    {currency(
                      completed
                        .filter((a) => a.branch_id === b.id)
                        .reduce((sum, a) => sum + a.price_kopecks, 0),
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="analytics-note">
        <CircleHelp size={16} />
        Стоимость услуг не подтверждает получение оплаты. Финансовый учёт и
        эквайринг подключаются отдельно.
      </p>
    </>
  );
}

export function DevSimulator({ onSaved }: { onSaved: () => void }) {
  const [event, setEvent] = useState("new_lead");
  const [advance, setAdvance] = useState(0);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState("");
  const toast = useToast();
  async function simulate() {
    setBusy(true);
    try {
      const r = await post<{ message: string }>("/dev/simulate", {
        event,
        advance_minutes: advance,
      });
      setResult(
        r.message || "Событие создано. Проверьте соответствующий раздел.",
      );
      onSaved();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="panel simulator-panel">
      <div>
        <span className="round-icon">
          <FlaskConical size={25} />
        </span>
        <h2>Симулятор событий</h2>
        <p>
          Создаёт учебное событие в тестовой клинике. Изменения появятся в
          календаре, CRM, задачах и диалогах.
        </p>
      </div>
      <div className="form-grid">
        <Field label="Какое событие создать">
          <select value={event} onChange={(e) => setEvent(e.target.value)}>
            {[
              ["new_lead", "Новое обращение"],
              ["cancel", "Отмена записи"],
              ["missed_reply", "Пропущенный ответ"],
              ["task", "Новая задача"],
              ["free_slot", "Освободившееся время"],
              ["reminder", "Напоминание"],
              ["handoff", "Передача человеку"],
            ].map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Сдвиг тестового времени, мин."
          hint="Помогает проверить ожидание и напоминания."
        >
          <input
            type="number"
            min={0}
            max={525600}
            value={advance}
            onChange={(e) => setAdvance(Number(e.target.value))}
          />
        </Field>
      </div>
      <Button onClick={simulate} loading={busy}>
        <FlaskConical size={17} />
        Создать событие
      </Button>
      {result && (
        <div className="success-note">
          <CheckCircle2 size={19} />
          {result}
        </div>
      )}
      <p className="muted">
        Сброс стенда доступен владельцу платформы в глобальной панели. Он
        требует отдельного подтверждения.
      </p>
    </div>
  );
}

export function AdminApp() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [section, setSection] = useState("overview");
  const [search, setSearch] = useState("");
  const [mobile, setMobile] = useState(false);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [booking, setBooking] = useState(false);
  const [reschedule, setReschedule] = useState<Appointment | null>(null);
  const [selected, setSelected] = useState<Appointment | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [schedules, setSchedules] = useState<Row[]>([]);
  const router = useRouter();
  const toast = useToast();
  const refresh = useCallback(async () => {
    try {
      const value = await api<Bootstrap>("/admin/bootstrap");
      setData(value);
      setError("");
      if (value.schedules) setSchedules(value.schedules);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.replace("/login");
        return;
      }
      if (e instanceof ApiError && e.status === 403) {
        const current = await api<{ user: User }>("/auth/me").catch(() => null);
        if (current?.user.role === "super_admin") {
          router.replace("/super");
          return;
        }
        if (current?.user.role === "patient") {
          router.replace("/clinic/smile-avenue");
          return;
        }
      }
      setError(errorText(e));
    }
  }, [router]);
  useEffect(() => {
    refresh();
    api<Config>("/public/config")
      .then(setConfig)
      .catch(() => {});
    const initial = window.location.hash.slice(1);
    if ([...navItems.map((n) => n.id), "schedules", "dev"].includes(initial))
      setSection(initial);
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, 20000);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    if (section === "schedules")
      api<{ items: Row[] }>("/admin/schedules")
        .then((v) => setSchedules(v.items))
        .catch((e) => toast(errorText(e), "error"));
  }, [section, toast]);
  function navigate(id: string) {
    setSection(id);
    setSearch("");
    setMobile(false);
    window.history.replaceState(null, "", `/admin#${id}`);
  }
  async function logout() {
    try {
      await post("/auth/logout");
      router.push("/login");
    } catch (e) {
      toast(errorText(e), "error");
    }
  }
  async function manualRefresh() {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }
  if (!data)
    return (
      <div className="app-loading">
        <Logo />
        <Loading text="Открываем рабочее пространство…" />
        <ErrorNote message={error} />
        {error && (
          <Button variant="secondary" onClick={refresh}>
            Повторить
          </Button>
        )}
      </div>
    );
  const canManage = ["owner", "manager"].includes(data.user.role);
  const isDoctor = data.user.role === "doctor";
  const clinic = data;
  const options = (rows: Row[]) =>
    rows.map((r) => ({ value: r.id, label: String(r.name || r.title) }));
  const visibleNav = navItems.filter((n) =>
    isDoctor
      ? [
          "overview",
          "calendar",
          "appointments",
          "patients",
          "doctors",
          "services",
          "branches",
          "analytics",
        ].includes(n.id)
      : ["automations", "ai", "settings"].includes(n.id)
        ? canManage
        : n.id === "employees"
          ? data.user.role === "owner"
          : true,
  );
  const title =
    navItems.find((n) => n.id === section)?.label ||
    { schedules: "Рабочие часы", dev: "Тестовый стенд" }[section] ||
    "Обзор";
  const allowed =
    visibleNav.some((n) => n.id === section) ||
    (section === "schedules" && canManage) ||
    (section === "dev" && canManage && config?.dev_tools);
  const rowMatch = (r: Row) =>
    !search ||
    Object.values(r).some((v) =>
      String(v).toLowerCase().includes(search.toLowerCase()),
    );
  const afterSave = () => {
    refresh();
    if (section === "schedules")
      api<{ items: Row[] }>("/admin/schedules")
        .then((v) => setSchedules(v.items))
        .catch((e) => toast(errorText(e), "error"));
  };
  const doctorFields: FormField[] = [
    { name: "name", label: "ФИО врача", required: true },
    {
      name: "specialty",
      label: "Специализация",
      required: true,
      defaultValue: "Стоматолог",
    },
    {
      name: "branch_id",
      label: "Филиал",
      type: "select",
      required: true,
      options: options(data.branches),
    },
    {
      name: "color",
      label: "Цвет в расписании",
      type: "color",
      defaultValue: "#087f8c",
    },
    {
      name: "service_ids",
      label: "Услуги врача",
      type: "multiselect",
      options: options(data.services),
    },
    { name: "active", label: "Врач активен", type: "checkbox" },
  ];
  const serviceFields: FormField[] = [
    { name: "name", label: "Название услуги", required: true },
    {
      name: "category",
      label: "Категория",
      required: true,
      defaultValue: "Стоматология",
    },
    { name: "description", label: "Описание", type: "textarea" },
    {
      name: "duration_minutes",
      label: "Длительность, минут",
      type: "number",
      min: 15,
      max: 480,
      defaultValue: 30,
      required: true,
      hint: "Укажите число, кратное 15.",
    },
    {
      name: "price_kopecks",
      label: "Стоимость, ₽",
      type: "money",
      min: 0,
      max: 10000000,
      defaultValue: 0,
      required: true,
    },
    { name: "active", label: "Показывать на сайте", type: "checkbox" },
  ];
  const taskFields: FormField[] = [
    { name: "title", label: "Задача", required: true },
    { name: "description", label: "Описание", type: "textarea" },
    {
      name: "status",
      label: "Статус",
      type: "select",
      required: true,
      defaultValue: "open",
      options: ["open", "in_progress", "done"].map((s) => ({
        value: s,
        label: statuses[s],
      })),
    },
    { name: "due_at", label: "Срок (МСК)", type: "datetime-local" },
    {
      name: "assigned_to",
      label: "Ответственный",
      type: "select",
      options: options(data.staff),
    },
    {
      name: "patient_id",
      label: "Пациент",
      type: "select",
      options: options(data.patients),
    },
  ];
  const scheduleFields: FormField[] = [
    {
      name: "doctor_id",
      label: "Врач",
      type: "select",
      required: true,
      options: options(data.doctors),
    },
    {
      name: "branch_id",
      label: "Филиал",
      type: "select",
      required: true,
      options: options(data.branches),
    },
    {
      name: "weekday",
      label: "День недели",
      type: "select",
      required: true,
      defaultValue: "0",
      options: [
        "Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота",
        "Воскресенье",
      ].map((label, i) => ({ value: String(i), label })),
    },
    {
      name: "start_time",
      label: "Начало работы (МСК)",
      type: "time",
      required: true,
      defaultValue: "09:00",
    },
    {
      name: "end_time",
      label: "Конец работы (МСК)",
      type: "time",
      required: true,
      defaultValue: "18:00",
    },
    { name: "break_start", label: "Перерыв с", type: "time" },
    { name: "break_end", label: "Перерыв до", type: "time" },
    { name: "active", label: "Рабочая смена активна", type: "checkbox" },
  ];
  return (
    <div className="admin-shell">
      <aside className={`app-sidebar ${mobile ? "mobile-open" : ""}`}>
        <Link href="/" className="sidebar-logo">
          <Logo />
        </Link>
        <div className="sidebar-clinic">
          <span className="clinic-icon">
            <Building2 size={18} />
          </span>
          <div>
            <strong>{data.tenant.name}</strong>
            <span>Рабочее пространство</span>
          </div>
          <Badge tone="green">RU</Badge>
        </div>
        <div className="sidebar-nav">
          <span className="nav-group-label">РАБОЧЕЕ ПРОСТРАНСТВО</span>
          {visibleNav.map((n, i) => (
            <div key={n.id}>
              {i === 7 && (
                <span className="nav-group-label management-label">
                  УПРАВЛЕНИЕ
                </span>
              )}
              <button
                className={section === n.id ? "active" : ""}
                onClick={() => navigate(n.id)}
              >
                <n.icon size={18} />
                <span>{n.label}</span>
                {n.id === "tasks" &&
                  data.tasks.filter((t) => t.status !== "done").length > 0 && (
                    <small>
                      {data.tasks.filter((t) => t.status !== "done").length}
                    </small>
                  )}
                {n.id === "conversations" &&
                  data.conversations.some((c) => c.mode === "human") && (
                    <i className="nav-notification-dot" />
                  )}
              </button>
            </div>
          ))}
          {config?.dev_tools && canManage && (
            <button
              className={`dev-nav ${section === "dev" ? "active" : ""}`}
              onClick={() => navigate("dev")}
            >
              <FlaskConical size={18} />
              <span>Тестовый стенд</span>
            </button>
          )}
        </div>
        <div className="sidebar-bottom">
          <a
            href={`/clinic/${data.tenant.slug}`}
            target="_blank"
            rel="noreferrer"
          >
            <GlobeIcon />
            Сайт клиники
            <ArrowUpRight size={15} />
          </a>
          <div className="sidebar-user">
            <Avatar name={data.user.name} small />
            <div>
              <strong>{data.user.name}</strong>
              <span>{roles[data.user.role]}</span>
            </div>
            <button
              className="icon-btn"
              aria-label="Выйти из аккаунта"
              title="Выйти"
              onClick={logout}
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {mobile && (
        <button
          className="sidebar-backdrop"
          aria-label="Закрыть навигацию"
          onClick={() => setMobile(false)}
        />
      )}
      <div className="app-main">
        <header className="app-topbar">
          <div className="topbar-breadcrumb">
            <button
              className="mobile-nav-toggle icon-btn"
              aria-label="Открыть навигацию"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={20} />
            </button>
            <span>{data.tenant.name}</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-actions">
            <div className="global-search">
              <Search size={16} />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Поиск в разделе"
                aria-label="Поиск в текущем разделе"
              />
              {search && (
                <button
                  aria-label="Очистить поиск"
                  onClick={() => setSearch("")}
                >
                  <X size={14} />
                </button>
              )}
            </div>
            <button
              className={`icon-btn ${refreshing ? "spin" : ""}`}
              title="Обновить данные"
              aria-label="Обновить данные"
              onClick={manualRefresh}
            >
              <RefreshCw size={18} />
            </button>
            <button
              className="notification-button icon-btn"
              aria-label="Показать уведомления"
              onClick={() => setNotificationOpen(true)}
            >
              <Bell size={19} />
              {data.notifications.length > 0 && <i />}
            </button>
            <Avatar name={data.user.name} small />
          </div>
        </header>
        {config?.dev_tools && (
          <div className="app-dev-strip">
            <span>
              <FlaskConical size={14} />
              Тестовый стенд · вымышленные данные
            </span>
            <a
              href={`/clinic/${data.tenant.slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Режим пациента <ArrowUpRight size={14} />
            </a>
          </div>
        )}
        <main className="admin-content">
          <ErrorNote message={error} />
          <div className="admin-page-heading">
            <div>
              <span className="admin-eyebrow">
                {section === "overview"
                  ? dateLabel(new Date(), { weekday: "long", year: "numeric" })
                  : "DENTFLOW · " + data.tenant.name.toUpperCase()}
              </span>
              <h1>
                {section === "overview"
                  ? `Добрый день, ${data.user.name.split(" ")[0]}`
                  : title}
                {section === "overview" && <span className="greeting-dot" />}
              </h1>
              <p>
                {section === "overview"
                  ? "Вот что происходит в вашей клинике сегодня."
                  : section === "calendar"
                    ? "Каждый визит на своём месте."
                    : section === "appointments"
                      ? "Записи со всех каналов в одном списке."
                      : undefined}
              </p>
            </div>
            {!isDoctor &&
              ["overview", "calendar", "appointments"].includes(section) && (
                <Button
                  onClick={() => {
                    setReschedule(null);
                    setBooking(true);
                  }}
                >
                  <Plus size={18} />
                  Новая запись
                </Button>
              )}
          </div>
          {!allowed ? (
            <Empty
              title="Раздел недоступен для вашей роли"
              text="Доступ выдаётся владельцем клиники."
            >
              <Button variant="secondary" onClick={() => navigate("overview")}>
                Вернуться к обзору
              </Button>
            </Empty>
          ) : (
            <>
              {section === "overview" && (
                <Overview
                  data={data}
                  onNavigate={navigate}
                  onSelect={setSelected}
                  onSaved={refresh}
                />
              )}
              {section === "calendar" && (
                <Calendar
                  appointments={data.appointments.filter(rowMatch)}
                  doctors={data.doctors}
                  branches={data.branches}
                  onSelect={setSelected}
                  onSchedules={() => navigate("schedules")}
                  canManage={canManage}
                />
              )}
              {section === "appointments" && (
                <div className="panel table-panel">
                  <div className="table-toolbar">
                    <span>{data.appointments.length} записей в базе</span>
                    <select
                      aria-label="Фильтр по статусу"
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                    >
                      <option value="">Все статусы</option>
                      {[
                        "scheduled",
                        "confirmed",
                        "completed",
                        "cancelled",
                        "no_show",
                      ].map((s) => (
                        <option value={s} key={s}>
                          {statuses[s]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <AppointmentTable
                    appointments={data.appointments.filter(
                      (a) =>
                        (!statusFilter || a.status === statusFilter) &&
                        rowMatch(a),
                    )}
                    onSelect={setSelected}
                  />
                </div>
              )}
              {section === "patients" && (
                <>
                  <div className="patient-segments">
                    {Array.from(
                      new Set(data.patients.map((p) => p.segment)),
                    ).map((s) => (
                      <div className="panel" key={s}>
                        <span>{s || "Без сегмента"}</span>
                        <strong>
                          {data.patients.filter((p) => p.segment === s).length}
                        </strong>
                      </div>
                    ))}
                  </div>
                  <div className="panel table-panel">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Пациент</th>
                            <th>Телефон</th>
                            <th>Сегмент</th>
                            <th>Записей</th>
                            <th>Уведомления</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {data.patients.filter(rowMatch).map((p) => (
                            <tr key={p.id}>
                              <td>
                                <div className="cell-person">
                                  <Avatar name={p.name} />
                                  <strong>{p.name}</strong>
                                </div>
                              </td>
                              <td>{p.phone}</td>
                              <td>
                                <Badge>{p.segment || "Новый"}</Badge>
                              </td>
                              <td>
                                {
                                  data.appointments.filter(
                                    (a) => a.patient_id === p.id,
                                  ).length
                                }
                              </td>
                              <td>
                                <Badge
                                  tone={
                                    p.notifications_enabled
                                      ? "green"
                                      : "neutral"
                                  }
                                >
                                  {p.notifications_enabled
                                    ? "Разрешены"
                                    : "Выключены"}
                                </Badge>
                              </td>
                              <td>
                                <button
                                  className="text-btn"
                                  onClick={() => setPatient(p)}
                                >
                                  Карточка
                                  <ArrowUpRight size={14} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {!data.patients.filter(rowMatch).length && <Empty />}
                  </div>
                </>
              )}
              {section === "crm" && (
                <CRM data={data} onSaved={refresh} search={search} />
              )}
              {section === "conversations" && (
                <Conversations
                  conversations={data.conversations}
                  onSaved={refresh}
                  search={search}
                />
              )}
              {section === "tasks" && (
                <ResourceManager
                  title="Задачи команды"
                  description="Сроки, ответственные и следующий шаг по каждому обращению."
                  singular="Новая задача"
                  resource="tasks"
                  rows={data.tasks}
                  fields={taskFields}
                  canEdit
                  onSaved={refresh}
                  search={search}
                  columns={[
                    {
                      key: "title",
                      label: "Задача",
                      render: (r) => (
                        <>
                          <strong>{String(r.title)}</strong>
                          <small>{String(r.description || "")}</small>
                        </>
                      ),
                    },
                    {
                      key: "due_at",
                      label: "Срок",
                      render: (r) =>
                        r.due_at
                          ? `${dateLabel(String(r.due_at), { month: "short" })}, ${time(String(r.due_at))}`
                          : "Без срока",
                    },
                    {
                      key: "assigned_to",
                      label: "Ответственный",
                      render: (r) =>
                        String(
                          data.staff.find((s) => s.id === r.assigned_to)
                            ?.name || "Не назначен",
                        ),
                    },
                    {
                      key: "status",
                      label: "Статус",
                      render: (r) => <Status value={String(r.status)} />,
                    },
                  ]}
                />
              )}
              {section === "doctors" && (
                <ResourceManager
                  title="Врачи клиники"
                  description="Специализация, филиал и услуги каждого специалиста."
                  singular="Добавить врача"
                  resource="doctors"
                  rows={data.doctors}
                  fields={doctorFields}
                  canEdit={canManage}
                  onSaved={refresh}
                  search={search}
                  columns={[
                    {
                      key: "name",
                      label: "Врач",
                      render: (r) => (
                        <div className="cell-person">
                          <Avatar
                            name={String(r.name)}
                            color={String(r.color || "#087f8c")}
                          />
                          <strong>{String(r.name)}</strong>
                        </div>
                      ),
                    },
                    { key: "specialty", label: "Специализация" },
                    {
                      key: "branch_id",
                      label: "Филиал",
                      render: (r) =>
                        data.branches.find((b) => b.id === r.branch_id)?.name ||
                        "—",
                    },
                    {
                      key: "service_ids",
                      label: "Услуг",
                      render: (r) =>
                        Array.isArray(r.service_ids) ? r.service_ids.length : 0,
                    },
                    {
                      key: "active",
                      label: "Статус",
                      render: (r) => (
                        <Badge tone={r.active ? "green" : "neutral"}>
                          {r.active ? "Активен" : "Отключён"}
                        </Badge>
                      ),
                    },
                  ]}
                  extra={
                    canManage && (
                      <div className="catalog-notice">
                        <Clock3 size={18} />
                        Чтобы врач был доступен для записи, задайте его рабочие
                        часы.
                        <button
                          className="text-btn"
                          onClick={() => navigate("schedules")}
                        >
                          Настроить расписание
                          <ArrowRight size={15} />
                        </button>
                      </div>
                    )
                  }
                />
              )}
              {section === "services" && (
                <ResourceManager
                  title="Прайс-лист"
                  description="Актуальные цены используются на сайте и в диалогах помощника."
                  singular="Добавить услугу"
                  resource="services"
                  rows={data.services}
                  fields={serviceFields}
                  canEdit={canManage}
                  onSaved={refresh}
                  search={search}
                  columns={[
                    {
                      key: "name",
                      label: "Услуга",
                      render: (r) => <strong>{String(r.name)}</strong>,
                    },
                    { key: "category", label: "Категория" },
                    {
                      key: "duration_minutes",
                      label: "Длительность",
                      render: (r) => `${r.duration_minutes} мин.`,
                    },
                    {
                      key: "price_kopecks",
                      label: "Стоимость",
                      render: (r) => (
                        <strong>{currency(Number(r.price_kopecks))}</strong>
                      ),
                    },
                    {
                      key: "active",
                      label: "На сайте",
                      render: (r) => (
                        <Badge tone={r.active ? "green" : "neutral"}>
                          {r.active ? "Опубликована" : "Скрыта"}
                        </Badge>
                      ),
                    },
                  ]}
                />
              )}
              {section === "branches" && (
                <ResourceManager
                  title="Филиалы"
                  description="Адреса и контакты для пациентов."
                  singular="Добавить филиал"
                  resource="branches"
                  rows={data.branches}
                  fields={[
                    { name: "name", label: "Название", required: true },
                    { name: "address", label: "Адрес", required: true },
                    { name: "phone", label: "Телефон" },
                    {
                      name: "active",
                      label: "Филиал активен",
                      type: "checkbox",
                    },
                  ]}
                  canEdit={canManage}
                  onSaved={refresh}
                  search={search}
                  columns={[
                    {
                      key: "name",
                      label: "Филиал",
                      render: (r) => <strong>{String(r.name)}</strong>,
                    },
                    { key: "address", label: "Адрес" },
                    { key: "phone", label: "Телефон" },
                    {
                      key: "active",
                      label: "Статус",
                      render: (r) => (
                        <Badge tone={r.active !== false ? "green" : "neutral"}>
                          {r.active !== false ? "Активен" : "Отключён"}
                        </Badge>
                      ),
                    },
                  ]}
                />
              )}
              {section === "schedules" && (
                <ResourceManager
                  title="Рабочие часы врачей"
                  description="Повторяющиеся смены по дням недели, включая перерывы. Время московское."
                  singular="Добавить смену"
                  resource="schedules"
                  rows={schedules}
                  fields={scheduleFields}
                  canEdit={canManage}
                  onSaved={afterSave}
                  search={search}
                  columns={[
                    {
                      key: "doctor_id",
                      label: "Врач",
                      render: (r) =>
                        data.doctors.find((d) => d.id === r.doctor_id)?.name ||
                        "—",
                    },
                    {
                      key: "weekday",
                      label: "День",
                      render: (r) =>
                        ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][
                          Number(r.weekday)
                        ],
                    },
                    {
                      key: "start_time",
                      label: "Часы",
                      render: (r) => `${r.start_time}–${r.end_time}`,
                    },
                    {
                      key: "break_start",
                      label: "Перерыв",
                      render: (r) =>
                        r.break_start
                          ? `${r.break_start}–${r.break_end}`
                          : "Нет",
                    },
                    {
                      key: "active",
                      label: "Статус",
                      render: (r) => (
                        <Badge tone={r.active ? "green" : "neutral"}>
                          {r.active ? "Активна" : "Отключена"}
                        </Badge>
                      ),
                    },
                  ]}
                />
              )}
              {section === "automations" && (
                <Automations
                  data={data}
                  onSaved={refresh}
                  devTools={Boolean(config?.dev_tools)}
                />
              )}
              {section === "ai" && <AISettings data={data} onSaved={refresh} />}
              {section === "analytics" && <Analytics data={data} />}
              {section === "integrations" && <Integrations data={data} />}
              {section === "employees" && (
                <ResourceManager
                  title="Команда клиники"
                  description="Учётные записи и права доступа. Новый пароль должен содержать не менее 12 символов."
                  singular="Добавить сотрудника"
                  resource="employees"
                  rows={data.staff}
                  fields={[
                    { name: "name", label: "Имя", required: true },
                    {
                      name: "email",
                      label: "Email",
                      type: "email",
                      required: true,
                    },
                    {
                      name: "password",
                      label: "Пароль",
                      type: "password",
                      hint: "При редактировании оставьте пустым, чтобы сохранить текущий.",
                    },
                    {
                      name: "role",
                      label: "Роль",
                      type: "select",
                      required: true,
                      defaultValue: "administrator",
                      options: ["manager", "administrator", "doctor"].map(
                        (value) => ({ value, label: roles[value] }),
                      ),
                    },
                    {
                      name: "doctor_id",
                      label: "Профиль врача (для роли «Врач»)",
                      type: "select",
                      options: options(data.doctors),
                    },
                    {
                      name: "active",
                      label: "Доступ включён",
                      type: "checkbox",
                    },
                  ]}
                  canEdit
                  canEditRow={(r) => r.role !== "owner"}
                  onSaved={refresh}
                  search={search}
                  columns={[
                    {
                      key: "name",
                      label: "Сотрудник",
                      render: (r) => (
                        <div className="cell-person">
                          <Avatar name={String(r.name)} small />
                          <strong>{String(r.name)}</strong>
                        </div>
                      ),
                    },
                    { key: "email", label: "Email" },
                    {
                      key: "role",
                      label: "Роль",
                      render: (r) => roles[String(r.role)] || String(r.role),
                    },
                    {
                      key: "active",
                      label: "Доступ",
                      render: (r) => (
                        <Badge tone={r.active ? "green" : "red"}>
                          {r.active ? "Включён" : "Выключен"}
                        </Badge>
                      ),
                    },
                  ]}
                />
              )}
              {section === "settings" && (
                <ClinicSettings data={data} onSaved={refresh} />
              )}
              {section === "dev" && <DevSimulator onSaved={refresh} />}
            </>
          )}
        </main>
      </div>
      {booking && (
        <BookingModal
          open
          onClose={() => setBooking(false)}
          clinic={clinic}
          patients={data.patients}
          admin
          appointment={reschedule}
          onCreated={refresh}
        />
      )}
      <AppointmentDetails
        appointment={selected}
        onClose={() => setSelected(null)}
        onSaved={refresh}
        onReschedule={(a) => {
          setSelected(null);
          setReschedule(a);
          setBooking(true);
        }}
        canReschedule={!isDoctor}
      />
      <Modal
        open={Boolean(patient)}
        onClose={() => setPatient(null)}
        title={patient?.name || "Карточка пациента"}
        wide
      >
        {patient && (
          <div className="patient-detail">
            <div className="patient-detail-head">
              <Avatar name={patient.name} />
              <div>
                <h3>{patient.name}</h3>
                <p>{patient.phone}</p>
                <Badge>{patient.segment}</Badge>
              </div>
            </div>
            <h3>История записей</h3>
            <AppointmentTable
              appointments={data.appointments.filter(
                (a) => a.patient_id === patient.id,
              )}
              onSelect={(a) => {
                setPatient(null);
                setSelected(a);
              }}
            />
            <h3>Организационная информация</h3>
            <p>
              Уведомления{" "}
              {patient.notifications_enabled ? "разрешены" : "отключены"}. В
              карточке представлены данные для организации визитов.
            </p>
            <p className="muted">
              Медицинские карты и диагнозы в этом кабинете не ведутся.
            </p>
          </div>
        )}
      </Modal>
      <Modal
        open={notificationOpen}
        title="Уведомления клиники"
        description="События и очередь сообщений"
        onClose={() => setNotificationOpen(false)}
      >
        {data.notifications.length ? (
          data.notifications.slice(0, 30).map((n) => (
            <div className="notification-item" key={n.id}>
              <span className="round-icon">
                <Bell size={17} />
              </span>
              <div>
                <strong>{String(n.title || "Уведомление")}</strong>
                <p>{String(n.body || n.text || "")}</p>
                <Status value={String(n.status || "pending")} />
              </div>
            </div>
          ))
        ) : (
          <Empty
            title="Уведомлений пока нет"
            text="Здесь появятся события по записям и обращениям."
          />
        )}
      </Modal>
    </div>
  );
}

function GlobeIcon() {
  return <Building2 size={16} />;
}
function AppointmentDetails({
  appointment,
  onClose,
  onSaved,
  onReschedule,
  canReschedule,
}: {
  appointment: Appointment | null;
  onClose: () => void;
  onSaved: () => void;
  onReschedule: (a: Appointment) => void;
  canReschedule: boolean;
}) {
  return (
    <Modal
      open={Boolean(appointment)}
      onClose={onClose}
      title="Карточка записи"
    >
      {appointment && (
        <AppointmentDetailForm
          key={appointment.id}
          appointment={appointment}
          onClose={onClose}
          onSaved={onSaved}
          onReschedule={onReschedule}
          canReschedule={canReschedule}
        />
      )}
    </Modal>
  );
}
function AppointmentDetailForm({
  appointment: a,
  onClose,
  onSaved,
  onReschedule,
  canReschedule,
}: {
  appointment: Appointment;
  onClose: () => void;
  onSaved: () => void;
  onReschedule: (a: Appointment) => void;
  canReschedule: boolean;
}) {
  const [status, setStatus] = useState(a.status);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await patch(`/admin/appointments/${a.id}`, { status });
      onSaved();
      onClose();
      toast("Статус записи обновлён");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save}>
      <div className="appointment-detail-header">
        <Avatar name={a.patient_name} />
        <div>
          <h3>{a.patient_name}</h3>
          <span>{a.service_name}</span>
        </div>
        <Status value={a.status} />
      </div>
      <dl className="detail-list">
        <div>
          <dt>Дата и время</dt>
          <dd>
            {dateLabel(a.start_at)}, {time(a.start_at)}–{time(a.end_at)}
          </dd>
        </div>
        <div>
          <dt>Врач</dt>
          <dd>{a.doctor_name}</dd>
        </div>
        <div>
          <dt>Филиал</dt>
          <dd>{a.branch_name}</dd>
        </div>
        <div>
          <dt>Стоимость</dt>
          <dd>{currency(a.price_kopecks)}</dd>
        </div>
        <div>
          <dt>Источник</dt>
          <dd>
            {a.source === "web"
              ? "Онлайн-запись"
              : a.source === "telegram"
                ? "Telegram"
                : a.source === "manual"
                  ? "Администратор"
                  : "Демо"}
          </dd>
        </div>
      </dl>
      <Field
        label="Статус визита"
        hint={
          ["cancelled", "completed", "no_show"].includes(a.status)
            ? "Закрытый визит доступен для просмотра."
            : undefined
        }
      >
        <select
          disabled={["cancelled", "completed", "no_show"].includes(a.status)}
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {(canReschedule
            ? ["scheduled", "confirmed", "completed", "cancelled", "no_show"]
            : Array.from(
                new Set([a.status, "confirmed", "completed", "no_show"]),
              )
          ).map((s) => (
            <option
              value={s}
              key={s}
              disabled={
                !canReschedule &&
                !["confirmed", "completed", "no_show"].includes(s)
              }
            >
              {statuses[s]}
            </option>
          ))}
        </select>
      </Field>
      <ErrorNote message={error} />
      <div className="modal-actions">
        {canReschedule &&
        !["cancelled", "completed", "no_show"].includes(a.status) ? (
          <Button
            type="button"
            variant="secondary"
            onClick={() => onReschedule(a)}
          >
            <CalendarDays size={16} />
            Перенести
          </Button>
        ) : (
          <Button type="button" variant="secondary" onClick={onClose}>
            Закрыть
          </Button>
        )}
        <Button type="submit" loading={busy} disabled={status === a.status}>
          Сохранить
        </Button>
      </div>
    </form>
  );
}
