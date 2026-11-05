"use client";
import { useState } from "react";
import {
  Bot,
  Check,
  Code2,
  Copy,
  ExternalLink,
  Globe,
  Play,
  Settings2,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { Bootstrap, Row } from "@/lib/types";
import { errorText, patch, post } from "@/lib/api";
import { Badge, Button, ErrorNote, Field, Status, useToast } from "./ui";
import { FormField, ResourceManager } from "./resource-manager";
import { dateLabel, time } from "@/lib/format";

export function ClinicSettings({
  data,
  onSaved,
}: {
  data: Bootstrap;
  onSaved: () => void;
}) {
  const [values, setValues] = useState({
    name: data.tenant.name,
    description: String(data.tenant.description || ""),
    phone: String(data.tenant.phone || ""),
    brand_color: data.tenant.brand_color || "#087f8c",
    logo_url: String(data.tenant.logo_url || ""),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await patch("/admin/settings", { tenant: values });
      toast("Настройки клиники сохранены");
      onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Настройки клиники</h2>
          <p>Название и фирменный стиль на сайте пациентов.</p>
        </div>
      </div>
      <div className="settings-layout">
        <form className="panel settings-form" onSubmit={save}>
          <h3>
            <Settings2 size={18} />
            Основная информация
          </h3>
          <Field label="Название клиники">
            <input
              value={values.name}
              required
              minLength={2}
              maxLength={160}
              onChange={(e) =>
                setValues((v) => ({ ...v, name: e.target.value }))
              }
            />
          </Field>
          <Field label="Короткое описание">
            <textarea
              rows={4}
              maxLength={4000}
              value={values.description}
              onChange={(e) =>
                setValues((v) => ({ ...v, description: e.target.value }))
              }
            />
          </Field>
          <div className="form-grid">
            <Field label="Телефон клиники">
              <input
                type="tel"
                maxLength={30}
                value={values.phone}
                onChange={(e) =>
                  setValues((v) => ({ ...v, phone: e.target.value }))
                }
              />
            </Field>
            <Field label="Фирменный цвет">
              <div className="color-input">
                <input
                  type="color"
                  value={values.brand_color}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, brand_color: e.target.value }))
                  }
                />
                <span>{values.brand_color}</span>
              </div>
            </Field>
          </div>
          <Field
            label="Адрес логотипа"
            hint="Ссылка HTTPS на ваш собственный логотип. Оставьте пустым, чтобы использовать название."
          >
            <input
              type="url"
              placeholder="https://clinic.ru/logo.svg"
              value={values.logo_url}
              maxLength={500}
              onChange={(e) =>
                setValues((v) => ({ ...v, logo_url: e.target.value }))
              }
            />
          </Field>
          <ErrorNote message={error} />
          <Button type="submit" loading={busy}>
            Сохранить настройки
            <Check size={16} />
          </Button>
        </form>
        <aside>
          <div className="panel settings-note">
            <Globe size={24} />
            <h3>Сайт вашей клиники</h3>
            <p>
              Общие записи, врачи и услуги доступны пациентам на отдельной
              странице.
            </p>
            <a
              className="text-link"
              href={`/clinic/${data.tenant.slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Открыть сайт <ExternalLink size={15} />
            </a>
            <code>/clinic/{data.tenant.slug}</code>
            <p>
              Свой домен подключается настройкой DNS, HTTPS и маршрутизации на
              сервере. Порядок действий описан в инструкции развертывания.
            </p>
          </div>
          <div className="panel settings-note">
            <ShieldCheck size={24} />
            <h3>Работа с данными</h3>
            <p>
              Текущий часовой пояс интерфейса — Москва. Перед подключением
              пациентов разместите утверждённую политику и реквизиты оператора.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}

export function AISettings({
  data,
  onSaved,
}: {
  data: Bootstrap;
  onSaved: () => void;
}) {
  const [provider, setProvider] = useState(
    String(data.ai_settings?.provider || "demo"),
  );
  const [enabled, setEnabled] = useState(data.ai_settings?.enabled !== false);
  const [greeting, setGreeting] = useState(
    String(data.ai_settings?.greeting || ""),
  );
  const [knowledge, setKnowledge] = useState(
    String(data.ai_settings?.clinic_knowledge || ""),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await patch("/admin/settings", {
        ai_settings: {
          provider,
          enabled,
          greeting,
          clinic_knowledge: knowledge,
          handoff_medical: true,
        },
      });
      toast("Настройки помощника сохранены");
      onSaved();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>AI-администратор</h2>
          <p>Единая логика для веб-чата и Telegram.</p>
        </div>
        <Badge tone={provider === "demo" ? "amber" : "blue"}>
          {provider === "demo"
            ? "Алгоритмический демо-режим"
            : "Внешний провайдер требует настройки"}
        </Badge>
      </div>
      <div className="settings-layout">
        <form className="panel settings-form" onSubmit={save}>
          <h3>
            <Sparkles size={19} />
            Поведение помощника
          </h3>
          <label className="toggle-row">
            <span>
              <strong>Помощник включён</strong>
              <small>Возможность автоматически отвечать пациентам</small>
            </span>
            <input
              type="checkbox"
              role="switch"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
          </label>
          <Field label="Провайдер">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="demo">DEMO — без внешней LLM и ключей</option>
              <option value="yandex">YandexGPT — нужен ключ на сервере</option>
              <option value="gigachat">
                GigaChat — нужны доступ и настройки
              </option>
              <option value="local">
                Локальная модель — собственный сервер
              </option>
            </select>
          </Field>
          <Field label="Приветствие">
            <textarea
              rows={3}
              required
              minLength={2}
              maxLength={1000}
              value={greeting}
              onChange={(e) => setGreeting(e.target.value)}
            />
          </Field>
          <Field
            label="Административная база знаний"
            hint="Парковка, способы оплаты, правила визита. Не добавляйте медицинские документы или данные пациентов."
          >
            <textarea
              rows={8}
              value={knowledge}
              maxLength={20000}
              onChange={(e) => setKnowledge(e.target.value)}
              placeholder="Например: вход со двора, парковка рядом с клиникой…"
            />
          </Field>
          <ErrorNote message={error} />
          <Button type="submit" loading={busy}>
            Сохранить настройки
            <Check size={16} />
          </Button>
        </form>
        <aside>
          <div className="panel settings-note">
            <ShieldCheck size={24} />
            <h3>Безопасные границы</h3>
            <ul>
              <li>Цены и время берутся из базы.</li>
              <li>Запись подтверждается после сохранения.</li>
              <li>Медицинские вопросы передаются человеку.</li>
              <li>Ключи хранятся только на сервере.</li>
            </ul>
          </div>
          <div className="panel settings-note">
            <Bot size={24} />
            <h3>Проверяйте подключение</h3>
            <p>
              Выбор провайдера здесь не создаёт ключ и не активирует договор.
              Настройте переменные окружения и выполните проверку по
              AI_CONFIGURATION.md.
            </p>
            <a
              className="text-link"
              href={`/clinic/${data.tenant.slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Открыть веб-чат
              <ExternalLink size={15} />
            </a>
          </div>
        </aside>
      </div>
    </>
  );
}

export function Integrations({ data }: { data: Bootstrap }) {
  const toast = useToast();
  const [instructions, setInstructions] = useState("");
  async function copyWidget() {
    const code = `<script src="${window.location.origin}/widget.js" data-clinic="${data.tenant.slug}" defer></script>`;
    try {
      await navigator.clipboard.writeText(code);
      toast("Код виджета скопирован");
    } catch {
      setInstructions(code);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Интеграции</h2>
          <p>Статус каждого канала и системы отображается отдельно.</p>
        </div>
      </div>
      <div className="integration-admin-grid">
        {data.integrations.map((item) => (
          <article className="panel integration-admin-card" key={item.id}>
            <span className="integration-symbol">
              <Code2 size={24} />
            </span>
            <div>
              <h3>{String(item.name)}</h3>
              <Status value={String(item.status)} />
            </div>
            <p>{String(item.description || "")}</p>
            {Boolean(item.last_error) && (
              <ErrorNote message={String(item.last_error)} />
            )}
            <button
              className="text-btn"
              onClick={() =>
                setInstructions(
                  String(item.kind) === "telegram"
                    ? "Telegram: создайте бота в BotFather, добавьте TELEGRAM_BOT_TOKEN и TELEGRAM_CLINIC_SLUG на сервере, затем запустите сервис telegram. Точный порядок — в TELEGRAM_SETUP.md."
                    : String(item.kind) === "internal"
                      ? "Встроенное расписание использует PostgreSQL DentFlow. Врачи, услуги и рабочие часы управляются в соответствующих разделах."
                      : String(item.kind) === "payments"
                        ? "Режим DEMO не выполняет списаний. Подключение эквайринга и кассы — отдельный модуль после правовой и технической проверки."
                        : "Реальное подключение пока не заявлено. Изучите INTEGRATIONS.md: нужны доступ к API, договорные условия и проверка адаптера на тестовой МИС.",
                )
              }
            >
              Как подключить
              <ExternalLink size={14} />
            </button>
          </article>
        ))}
      </div>
      <div className="panel widget-settings">
        <div>
          <Code2 size={24} />
          <h3>Виджет для сайта клиники</h3>
          <p>
            Кнопка чата с единым движком. Для работы внутри iframe настройте его
            на домене клиники; отдельная вкладка доступна как запасной вариант.
          </p>
        </div>
        <Button variant="secondary" onClick={copyWidget}>
          <Copy size={16} />
          Скопировать код
        </Button>
      </div>
      {instructions && (
        <div className="panel integration-instructions">
          <h3>Инструкция</h3>
          <p>{instructions}</p>
          <button className="text-btn" onClick={() => setInstructions("")}>
            Скрыть
          </button>
        </div>
      )}
    </>
  );
}

export function Automations({
  data,
  onSaved,
  devTools,
}: {
  data: Bootstrap;
  onSaved: () => void;
  devTools: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [advance, setAdvance] = useState(0);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const toast = useToast();
  const kindNames: Record<string, string> = {
    reminder: "Напоминание",
    missed_reply: "Без ответа",
    feedback: "Обратная связь",
    reactivation: "Реактивация",
    waitlist: "Лист ожидания",
  };
  const fields: FormField[] = [
    { name: "name", label: "Название правила", required: true },
    {
      name: "kind",
      label: "Событие",
      type: "select",
      required: true,
      defaultValue: "reminder",
      onlyCreate: true,
      options: Object.entries(kindNames).map(([value, label]) => ({
        value,
        label,
      })),
    },
    {
      name: "delay_minutes",
      label: "Интервал, минут",
      type: "number",
      required: true,
      min: 1,
      max: 525600,
      defaultValue: 120,
      hint: "Для напоминаний — до визита; для остальных правил — период ожидания.",
    },
    {
      name: "enabled",
      label: "Правило включено",
      type: "checkbox",
      defaultValue: true,
    },
  ];
  async function run() {
    setBusy(true);
    try {
      setResult(
        await post("/admin/automations/run", {
          advance_minutes: devTools ? advance : 0,
        }),
      );
      onSaved();
      toast("Правила обработаны. Результат показан ниже.");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ResourceManager
        title="Автоматизации"
        description="Правила обрабатываются фоновым исполнителем и могут запускаться вручную."
        singular="Добавить правило"
        resource="automation_rules"
        rows={data.automation_rules}
        canEdit
        fields={fields}
        columns={[
          {
            key: "name",
            label: "Правило",
            render: (r) => <strong>{String(r.name)}</strong>,
          },
          {
            key: "kind",
            label: "Тип",
            render: (r) => kindNames[String(r.kind)] || String(r.kind),
          },
          {
            key: "delay_minutes",
            label: "Интервал",
            render: (r) => `${r.delay_minutes} мин.`,
          },
          {
            key: "enabled",
            label: "Состояние",
            render: (r) => (
              <Badge tone={r.enabled ? "green" : "neutral"}>
                {r.enabled ? "Включено" : "Отключено"}
              </Badge>
            ),
          },
        ]}
        onSaved={onSaved}
      />
      <div className="panel automation-run">
        <div>
          <span className="round-icon">
            <Zap size={23} />
          </span>
          <h3>Проверить правила сейчас</h3>
          <p>
            Создаст подходящие задачи и уведомления. Повторный запуск не должен
            дублировать одно и то же событие.
          </p>
        </div>
        {devTools && (
          <Field label="Сдвиг тестового времени, мин.">
            <input
              type="number"
              min={0}
              max={525600}
              value={advance}
              onChange={(e) => setAdvance(Number(e.target.value))}
            />
          </Field>
        )}
        <Button onClick={run} loading={busy}>
          <Play size={16} />
          Запустить
        </Button>
      </div>
      {result && (
        <div className="panel automation-result">
          <h3>Результат выполнения</h3>
          <div className="automation-counts">
            <span>
              Создано уведомлений{" "}
              <strong>{Number(result.notifications_created || 0)}</strong>
            </span>
            <span>
              Создано задач <strong>{Number(result.tasks_created || 0)}</strong>
            </span>
          </div>
        </div>
      )}
      <div className="panel-heading compact-heading">
        <div>
          <h2>Последние уведомления</h2>
          <p>Создание записи в очереди и доставка — разные события.</p>
        </div>
      </div>
      <div className="panel table-panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Сообщение</th>
                <th>Канал</th>
                <th>Статус</th>
                <th>Создано</th>
              </tr>
            </thead>
            <tbody>
              {data.notifications.slice(0, 30).map((n) => (
                <tr key={n.id}>
                  <td>
                    <strong>
                      {String(n.title || n.kind || "Уведомление")}
                    </strong>
                    <small>{String(n.body || n.text || "")}</small>
                  </td>
                  <td>{String(n.channel || "веб")}</td>
                  <td>
                    <Status value={String(n.status || "pending")} />
                  </td>
                  <td>
                    {n.created_at
                      ? `${dateLabel(String(n.created_at), { month: "short" })}, ${time(String(n.created_at))}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.notifications.length && (
            <p className="table-empty">Уведомлений пока нет.</p>
          )}
        </div>
      </div>
    </>
  );
}
