"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowRight,
  Building2,
  CheckCircle2,
  CreditCard,
  Download,
  FlaskConical,
  Globe,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError, errorText, post } from "@/lib/api";
import { Config, Row, Tenant, User } from "@/lib/types";
import { currency, dateLabel, shortNumber, time } from "@/lib/format";
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
import { FormField, RecordForm } from "./resource-manager";
import { DevSimulator } from "./admin-app";

type Overview = {
  tenants: Tenant[];
  plans: Row[];
  stats: Record<string, number | string>;
  connection_requests: Row[];
  integrations: Row[];
};
export function SuperApp() {
  const [data, setData] = useState<Overview | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [section, setSection] = useState("tenants");
  const [error, setError] = useState("");
  const [create, setCreate] = useState(false);
  const [editTenant, setEditTenant] = useState<Row | null>(null);
  const [editPlan, setEditPlan] = useState<Row | null>(null);
  const [reset, setReset] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState("");
  const router = useRouter();
  const toast = useToast();
  async function refresh() {
    try {
      const r = await api<Overview>("/super/overview");
      setData(r);
      setError("");
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(errorText(e));
    }
  }
  useEffect(() => {
    refresh();
    api<{ user: User }>("/auth/me")
      .then((r) => setUser(r.user))
      .catch(() => {});
    api<Config>("/public/config")
      .then(setConfig)
      .catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function logout() {
    try {
      await post("/auth/logout");
      router.push("/login");
    } catch (e) {
      toast(errorText(e), "error");
    }
  }
  async function healthCheck() {
    try {
      await api("/health");
      setHealth(`Сервер ответил успешно: ${time(new Date().toISOString())}`);
    } catch (e) {
      setHealth(errorText(e));
    }
  }
  async function resetData() {
    setBusy(true);
    try {
      await post("/dev/reset", { confirmation });
      setReset(false);
      setConfirmation("");
      toast("Тестовые данные восстановлены. Войдите заново.");
      router.replace("/login");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }
  const createFields: FormField[] = [
    { name: "name", label: "Название клиники", required: true },
    {
      name: "slug",
      label: "Адрес страницы",
      required: true,
      hint: "Латинские строчные буквы, цифры и дефисы, например smile-center.",
    },
    { name: "phone", label: "Телефон клиники" },
    { name: "owner_name", label: "Имя владельца клиники", required: true },
    {
      name: "owner_email",
      label: "Email владельца",
      type: "email",
      required: true,
    },
    {
      name: "owner_password",
      label: "Первый пароль владельца",
      type: "password",
      required: true,
      hint: "Не менее 12 символов. Передайте владельцу через защищённый канал.",
    },
    {
      name: "plan_code",
      label: "Тариф",
      type: "select",
      required: true,
      defaultValue: "BUSINESS",
      options: ["START", "BUSINESS", "ENTERPRISE"].map((value) => ({
        value,
        label: value,
      })),
    },
  ];
  if (!data)
    return (
      <div className="app-loading">
        <Logo />
        <Loading text="Открываем панель платформы…" />
        <ErrorNote message={error} />
        {error && (
          <>
            <Button variant="secondary" onClick={refresh}>
              Повторить
            </Button>
            <Link href="/login" className="text-link">
              Войти под другой ролью
            </Link>
          </>
        )}
      </div>
    );
  const tabs = [
    { id: "tenants", name: "Клиники", icon: Building2 },
    { id: "requests", name: "Заявки на подключение", icon: MessageCircle },
    { id: "plans", name: "Тарифы", icon: CreditCard },
    { id: "monitoring", name: "Мониторинг", icon: Activity },
    ...(config?.dev_tools
      ? [{ id: "dev", name: "Тестовый стенд", icon: FlaskConical }]
      : []),
  ];
  return (
    <div className="super-shell">
      <header className="super-header">
        <Link href="/">
          <Logo />
        </Link>
        <span className="super-label">
          <ShieldCheck size={16} />
          Управление платформой
        </span>
        <div>
          <Avatar name={user?.name || "Владелец платформы"} small />
          <button className="icon-btn" onClick={logout} aria-label="Выйти">
            <LogOut size={18} />
          </button>
        </div>
      </header>
      <main className="super-content">
        <div className="admin-page-heading">
          <div>
            <span className="eyebrow">DENTFLOW PLATFORM</span>
            <h1>Платформа под контролем</h1>
            <p>Клиники, подписки и состояние подключений.</p>
          </div>
          <Button onClick={() => setCreate(true)}>
            <Plus size={17} />
            Подключить клинику
          </Button>
        </div>
        <ErrorNote message={error} />
        <div className="metric-grid">
          <article className="metric-card">
            <div>
              <span>Подключено клиник</span>
              <Building2 size={19} />
            </div>
            <strong>
              {shortNumber(Number(data.stats.total_tenants || 0))}
            </strong>
            <small>{data.stats.active_tenants || 0} активных</small>
          </article>
          <article className="metric-card">
            <div>
              <span>Записей в платформе</span>
              <LayoutDashboard size={19} />
            </div>
            <strong>{shortNumber(Number(data.stats.appointments || 0))}</strong>
            <small>Только агрегированные показатели</small>
          </article>
          <article className="metric-card">
            <div>
              <span>Сообщений помощника</span>
              <MessageCircle size={19} />
            </div>
            <strong>{shortNumber(Number(data.stats.ai_messages || 0))}</strong>
            <small>По данным учёта использования</small>
          </article>
          <article className="metric-card">
            <div>
              <span>Настроенные подписки</span>
              <CreditCard size={19} />
            </div>
            <strong>
              {currency(
                Number(data.stats.configured_subscription_value_kopecks || 0),
              )}
            </strong>
            <small>DEMO · платежи не списываются</small>
          </article>
        </div>
        <div className="super-navigation">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={section === t.id ? "active" : ""}
              onClick={() => setSection(t.id)}
            >
              <t.icon size={17} />
              {t.name}
              {t.id === "requests" && data.connection_requests?.length > 0 && (
                <small>{data.connection_requests.length}</small>
              )}
            </button>
          ))}
          <button className="super-refresh" onClick={refresh}>
            <RefreshCw size={16} />
            Обновить
          </button>
        </div>
        {section === "tenants" && (
          <div className="panel table-panel">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Клиника</th>
                    <th>Статус</th>
                    <th>Подписка</th>
                    <th>Сайт</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.tenants.map((t) => {
                    const subscription = t.subscription as
                      | Record<string, unknown>
                      | undefined;
                    return (
                      <tr key={t.id}>
                        <td>
                          <div className="cell-person">
                            <span className="clinic-icon">
                              <Building2 size={18} />
                            </span>
                            <div>
                              <strong>{t.name}</strong>
                              <small>{t.slug}</small>
                            </div>
                          </div>
                        </td>
                        <td>
                          <Status value={t.status || "active"} />
                        </td>
                        <td>
                          <strong>
                            {String(
                              subscription?.plan_code || t.plan_code || "—",
                            )}
                          </strong>
                          <small>
                            Оплата:{" "}
                            {String(subscription?.payment_mode || "DEMO")}
                          </small>
                        </td>
                        <td>
                          <Link
                            className="text-link"
                            href={`/clinic/${t.slug}`}
                            target="_blank"
                          >
                            Открыть
                            <Globe size={14} />
                          </Link>
                        </td>
                        <td>
                          <button
                            className="text-btn"
                            onClick={() =>
                              setEditTenant({
                                ...t,
                                plan_code:
                                  subscription?.plan_code ||
                                  t.plan_code ||
                                  "BUSINESS",
                              })
                            }
                          >
                            <Pencil size={15} />
                            Управлять
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="super-access-note">
              <ShieldCheck size={18} />
              Панель владельца платформы не открывает медицинские записи и
              переписки пациентов клиник.
            </div>
          </div>
        )}
        {section === "requests" && (
          <div className="panel table-panel">
            {data.connection_requests?.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Клиника</th>
                      <th>Контакт</th>
                      <th>Телефон / email</th>
                      <th>Дата</th>
                      <th>Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.connection_requests.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <strong>{String(r.clinic_name)}</strong>
                        </td>
                        <td>{String(r.name)}</td>
                        <td>
                          <a
                            href={`tel:${String(r.phone).replace(/[^+0-9]/g, "")}`}
                          >
                            {String(r.phone)}
                          </a>
                          <small>{String(r.email || "")}</small>
                        </td>
                        <td>
                          {r.created_at
                            ? dateLabel(String(r.created_at), {
                                month: "short",
                                year: "numeric",
                              })
                            : "—"}
                        </td>
                        <td>
                          <Badge tone="blue">
                            {r.status === "new"
                              ? "Новая"
                              : String(r.status || "Новая")}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty
                title="Новых заявок пока нет"
                text="Заявки с публичного сайта появятся здесь."
              />
            )}
          </div>
        )}
        {section === "plans" && (
          <>
            <div className="super-plan-grid">
              {data.plans.map((p) => (
                <article className="panel super-plan" key={p.id}>
                  <Badge tone={p.code === "BUSINESS" ? "green" : "neutral"}>
                    {String(p.code)}
                  </Badge>
                  <h2>{String(p.name)}</h2>
                  <strong className="super-plan-price">
                    {currency(Number(p.price_kopecks))}
                    <small> / месяц</small>
                  </strong>
                  <dl>
                    <div>
                      <dt>Филиалов</dt>
                      <dd>{String(p.branch_limit)}</dd>
                    </div>
                    <div>
                      <dt>Настройка лимита AI</dt>
                      <dd>{shortNumber(Number(p.ai_limit))}</dd>
                    </div>
                  </dl>
                  <Button variant="secondary" onClick={() => setEditPlan(p)}>
                    <Pencil size={15} />
                    Изменить тариф
                  </Button>
                </article>
              ))}
            </div>
            <div className="catalog-notice">
              <CreditCard size={20} />
              DEMO: изменение тарифа обновляет конфигурацию подписки. Это не
              реальный платёж.
            </div>
          </>
        )}
        {section === "monitoring" && (
          <>
            <div className="monitoring-grid">
              <div className="panel monitor-card">
                <span className="round-icon">
                  <Activity size={23} />
                </span>
                <h3>Доступность API</h3>
                <p>
                  {health ||
                    "Запустите проверку, чтобы получить текущий ответ сервера."}
                </p>
                <Button variant="secondary" onClick={healthCheck}>
                  Проверить сейчас
                </Button>
              </div>
              <div className="panel monitor-card">
                <span className="round-icon">
                  <MessageCircle size={23} />
                </span>
                <h3>Очередь уведомлений</h3>
                <strong>{data.stats.pending_notifications || 0}</strong>
                <p>Сообщения, ожидающие обработки.</p>
              </div>
              <div className="panel monitor-card">
                <span className="round-icon">
                  <ShieldCheck size={23} />
                </span>
                <h3>Ошибки интеграций</h3>
                <strong>{data.stats.integration_errors || 0}</strong>
                <p>По последнему сохранённому состоянию.</p>
              </div>
            </div>
            <div className="panel table-panel">
              <div className="panel-inner-heading">
                <h3>Состояние интеграций</h3>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Клиника</th>
                      <th>Интеграция</th>
                      <th>Статус</th>
                      <th>Последняя ошибка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.integrations?.map((i, index) => (
                      <tr key={i.id || index}>
                        <td>{String(i.tenant_name)}</td>
                        <td>{String(i.name)}</td>
                        <td>
                          <Status value={String(i.status)} />
                        </td>
                        <td>{String(i.last_error || "—")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
        {section === "dev" && (
          <>
            <div className="dev-tools-banner">
              <FlaskConical size={23} />
              <div>
                <strong>Изолированный тестовый контур</strong>
                <p>
                  Учебная клиника Smile Avenue. Проверяйте процессы на
                  вымышленных данных.
                </p>
              </div>
              <Link
                href="/clinic/smile-avenue"
                className="btn btn-secondary"
                target="_blank"
              >
                Режим пациента
                <ArrowRight size={16} />
              </Link>
            </div>
            <DevSimulator onSaved={refresh} />
            <div className="panel reset-panel">
              <div>
                <h3>Восстановить тестовые данные</h3>
                <p>
                  Удалит созданные на стенде данные и вернёт исходную Smile
                  Avenue. Потребуется повторный вход.
                </p>
              </div>
              <Button variant="danger" onClick={() => setReset(true)}>
                <Trash2 size={16} />
                Сбросить тестовые данные
              </Button>
            </div>
            <div className="catalog-notice">
              <ShieldCheck size={18} />
              Для работы от имени сотрудника выйдите и войдите под тестовым
              администратором. Прямое переключение прав не выполняется.
            </div>
          </>
        )}
      </main>
      <Modal
        open={create}
        title="Подключить клинику"
        description="Будет создано отдельное рабочее пространство и учётная запись владельца."
        onClose={() => setCreate(false)}
      >
        <RecordForm
          fields={createFields}
          endpoint="/super/tenants"
          method="POST"
          onSaved={() => {
            setCreate(false);
            refresh();
          }}
          onCancel={() => setCreate(false)}
        />
      </Modal>
      <Modal
        open={Boolean(editTenant)}
        title="Управление клиникой"
        onClose={() => setEditTenant(null)}
      >
        {editTenant && (
          <RecordForm
            initial={editTenant}
            endpoint={`/super/tenants/${editTenant.id}`}
            method="PATCH"
            fields={[
              { name: "name", label: "Название", required: true },
              {
                name: "status",
                label: "Статус пространства",
                type: "select",
                required: true,
                options: [
                  { value: "active", label: "Активно" },
                  { value: "blocked", label: "Заблокировано" },
                ],
              },
              {
                name: "plan_code",
                label: "Тариф",
                type: "select",
                required: true,
                options: ["START", "BUSINESS", "ENTERPRISE"].map((value) => ({
                  value,
                  label: value,
                })),
              },
            ]}
            onSaved={() => {
              setEditTenant(null);
              refresh();
            }}
            onCancel={() => setEditTenant(null)}
          />
        )}
      </Modal>
      <Modal
        open={Boolean(editPlan)}
        title="Изменить параметры тарифа"
        onClose={() => setEditPlan(null)}
      >
        {editPlan && (
          <RecordForm
            initial={editPlan}
            endpoint={`/super/plans/${editPlan.code}`}
            method="PATCH"
            fields={[
              {
                name: "price_kopecks",
                label: "Стоимость в месяц, ₽",
                type: "money",
                required: true,
                min: 0,
              },
              {
                name: "branch_limit",
                label: "Лимит филиалов",
                type: "number",
                required: true,
                min: 1,
                max: 1000,
              },
              {
                name: "ai_limit",
                label: "Настройка лимита AI",
                type: "number",
                required: true,
                min: 0,
                max: 10000000,
              },
            ]}
            onSaved={() => {
              setEditPlan(null);
              refresh();
            }}
            onCancel={() => setEditPlan(null)}
          />
        )}
      </Modal>
      <Modal
        open={reset}
        title="Сбросить весь тестовый стенд?"
        onClose={() => setReset(false)}
      >
        <p>
          Созданные на стенде записи, диалоги и изменения будут удалены. Будут
          восстановлены учебные данные и тестовые аккаунты.
        </p>
        <Field label="Введите RESET SMILE AVENUE для подтверждения">
          <input
            autoComplete="off"
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder="RESET SMILE AVENUE"
          />
        </Field>
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setReset(false)}>
            Отмена
          </Button>
          <Button
            variant="danger"
            disabled={confirmation !== "RESET SMILE AVENUE"}
            loading={busy}
            onClick={resetData}
          >
            Сбросить стенд
          </Button>
        </div>
      </Modal>
    </div>
  );
}
