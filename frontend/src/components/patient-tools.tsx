"use client";
import { useEffect, useState } from "react";
import {
  Bell,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  Send,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, errorText, patch, post } from "@/lib/api";
import { Row } from "@/lib/types";
import { dateLabel, time } from "@/lib/format";
import { Button, Field, Modal, Status, useToast } from "./ui";

export function PatientTools({
  slug,
  version,
}: {
  slug: string;
  version: string;
}) {
  const [notifications, setNotifications] = useState<Row[]>([]);
  const [consents, setConsents] = useState({
    notifications_enabled: false,
    marketing_enabled: false,
  });
  const [telegram, setTelegram] = useState<{
    command: string;
    url: string | null;
    expires_at: string;
    note: string;
  } | null>(null);
  const [busy, setBusy] = useState("");
  const [settings, setSettings] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleteConfirmed, setDeleteConfirmed] = useState(false);
  const toast = useToast();
  const base = `/public/clinics/${encodeURIComponent(slug)}`;
  useEffect(() => {
    let alive = true;
    Promise.all([
      api<{ notifications: Row[] }>(`${base}/notifications`),
      api<typeof consents>(`${base}/consents`),
    ])
      .then(([n, c]) => {
        if (alive) {
          setNotifications(n.notifications);
          setConsents(c);
        }
      })
      .catch((e) => alive && toast(errorText(e), "error"));
    return () => {
      alive = false;
    };
  }, [base, version]); // eslint-disable-line react-hooks/exhaustive-deps
  async function link() {
    setBusy("telegram");
    try {
      setTelegram(await post(`${base}/telegram-link`));
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy("");
    }
  }
  async function saveConsent(e: React.FormEvent) {
    e.preventDefault();
    setBusy("consent");
    try {
      setConsents(
        await patch(`${base}/consents`, {
          notifications_enabled: consents.notifications_enabled,
          marketing_enabled: consents.marketing_enabled,
        }),
      );
      toast("Настройки уведомлений сохранены");
      setSettings(false);
    } catch (err) {
      toast(errorText(err), "error");
    } finally {
      setBusy("");
    }
  }
  async function exportData() {
    setBusy("export");
    try {
      const data = await api(`${base}/my-data`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "dentflow-my-data.json";
      a.click();
      URL.revokeObjectURL(url);
      toast("Файл с данными подготовлен");
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy("");
    }
  }
  async function requestDeletion() {
    setBusy("delete");
    try {
      const r = await post<{ message: string }>(`${base}/delete-my-data`, {
        confirmation: "DELETE MY DATA",
      });
      toast(r.message);
      setDeleteOpen(false);
      setSettings(false);
      setConsents({ notifications_enabled: false, marketing_enabled: false });
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy("");
    }
  }
  async function copy() {
    if (!telegram) return;
    try {
      await navigator.clipboard.writeText(telegram.command);
      toast("Команда скопирована");
    } catch {
      toast("Выделите команду ниже и скопируйте её вручную.", "error");
    }
  }
  return (
    <div className="patient-account-tools">
      <div className="patient-tools-bar">
        <span>
          <ShieldCheck size={17} />
          Ваши данные и уведомления
        </span>
        <div>
          <Button
            variant="secondary"
            loading={busy === "telegram"}
            onClick={link}
          >
            <Send size={15} />
            Связать Telegram
          </Button>
          <Button variant="secondary" onClick={() => setSettings(true)}>
            Настройки данных
          </Button>
        </div>
      </div>
      {notifications.length > 0 && (
        <div className="patient-updates">
          <h3>
            <Bell size={17} />
            Обновления по вашим визитам
          </h3>
          {notifications.slice(0, 5).map((n) => (
            <article key={n.id}>
              <div>
                <strong>{String(n.title || "Уведомление")}</strong>
                <p>{String(n.text || n.body || "")}</p>
                <small>
                  {n.created_at
                    ? `${dateLabel(String(n.created_at), { month: "short" })}, ${time(String(n.created_at))}`
                    : ""}
                </small>
              </div>
              <Status value={String(n.status || "pending")} />
            </article>
          ))}
        </div>
      )}
      <Modal
        open={Boolean(telegram)}
        title="Безопасно связать Telegram"
        description="Код действует 10 минут и используется один раз."
        onClose={() => setTelegram(null)}
      >
        {telegram && (
          <div className="telegram-link">
            <span className="round-icon">
              <Send size={24} />
            </span>
            <p>{telegram.note}</p>
            {telegram.url ? (
              <a
                className="btn btn-primary"
                href={telegram.url}
                target="_blank"
                rel="noreferrer"
              >
                Открыть своего бота
                <ExternalLink size={16} />
              </a>
            ) : (
              <div className="inline-note">
                Имя бота ещё не настроено. Владелец стенда должен подключить
                Telegram по инструкции.
              </div>
            )}
            <Field label="Или отправьте эту команду боту клиники">
              <input
                value={telegram.command}
                readOnly
                onFocus={(e) => e.target.select()}
                aria-label="Одноразовая команда Telegram"
              />
            </Field>
            <Button variant="secondary" onClick={copy}>
              <Copy size={16} />
              Скопировать команду
            </Button>
            <p className="muted">
              Не отправляйте команду другим людям. Связывание подтверждает
              доступ к этой записи и аккаунту бота.
            </p>
          </div>
        )}
      </Modal>
      <Modal
        open={settings}
        title="Ваши данные и согласия"
        onClose={() => setSettings(false)}
      >
        <form onSubmit={saveConsent}>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={consents.notifications_enabled}
              onChange={(e) =>
                setConsents((c) => ({
                  ...c,
                  notifications_enabled: e.target.checked,
                }))
              }
            />
            <span>Уведомления о записи и напоминания</span>
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={consents.marketing_enabled}
              onChange={(e) =>
                setConsents((c) => ({
                  ...c,
                  marketing_enabled: e.target.checked,
                }))
              }
            />
            <span>
              Сообщения с предложениями и приглашениями на повторный визит. Это
              отдельное добровольное согласие.
            </span>
          </label>
          <Button type="submit" loading={busy === "consent"}>
            Сохранить согласия
            <CheckCircle2 size={15} />
          </Button>
        </form>
        <div className="patient-data-actions">
          <h3>Управление данными</h3>
          <p>
            Вы можете скачать историю из своего профиля или передать клинике
            запрос на удаление.
          </p>
          <Button
            variant="secondary"
            loading={busy === "export"}
            onClick={exportData}
          >
            <Download size={16} />
            Скачать мои данные
          </Button>
          <button
            className="text-btn danger-text"
            onClick={() => {
              setSettings(false);
              setDeleteConfirmed(false);
              setDeleteOpen(true);
            }}
          >
            <Trash2 size={14} />
            Запросить удаление
          </button>
        </div>
      </Modal>
      <Modal
        open={deleteOpen}
        title="Отправить запрос на удаление?"
        onClose={() => setDeleteOpen(false)}
      >
        <p>
          Клиника получит задачу на проверку и удаление допустимых данных.
          Обязательные сроки хранения проверяет сотрудник. Рассылки будут
          отключены сразу.
        </p>
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={deleteConfirmed}
            onChange={(e) => setDeleteConfirmed(e.target.checked)}
          />
          <span>Подтверждаю отправку запроса в клинику.</span>
        </label>
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setDeleteOpen(false)}>
            Отмена
          </Button>
          <Button
            variant="danger"
            disabled={!deleteConfirmed}
            loading={busy === "delete"}
            onClick={requestDeletion}
          >
            Отправить запрос
          </Button>
        </div>
      </Modal>
    </div>
  );
}
