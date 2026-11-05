"use client";
import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Headphones,
  MessageCircle,
  RefreshCw,
  Send,
} from "lucide-react";
import { api, errorText, patch, post } from "@/lib/api";
import { Conversation, Message } from "@/lib/types";
import { time } from "@/lib/format";
import {
  Avatar,
  Badge,
  Button,
  Empty,
  ErrorNote,
  Loading,
  useToast,
} from "./ui";

export function Conversations({
  conversations,
  onSaved,
  search,
}: {
  conversations: Conversation[];
  onSaved: () => void;
  search: string;
}) {
  const [selected, setSelected] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  const list = useRef<HTMLDivElement>(null);
  const conversation = conversations.find((c) => c.id === selected);
  useEffect(() => {
    if (!selected && conversations.length) setSelected(conversations[0].id);
  }, [selected, conversations]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoading(true);
    setError("");
    const load = () =>
      api<{ messages: Message[] }>(`/admin/conversations/${selected}/messages`)
        .then((v) => {
          if (active) {
            setMessages(v.messages);
            setError("");
          }
        })
        .catch((e) => active && setError(errorText(e)))
        .finally(() => active && setLoading(false));
    load();
    const timer = setInterval(load, 10000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [selected]);
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [messages.length]);
  async function mode(value: string) {
    if (!selected) return;
    setBusy(true);
    try {
      await patch(`/admin/conversations/${selected}`, { mode: value });
      onSaved();
      toast(
        value === "human"
          ? "Вы подключились к диалогу"
          : "Диалог передан помощнику",
      );
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }
  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || !selected) return;
    setBusy(true);
    setError("");
    try {
      await post(`/admin/conversations/${selected}/messages`, {
        text: text.trim(),
      });
      setText("");
      const result = await api<{ messages: Message[] }>(
        `/admin/conversations/${selected}/messages`,
      );
      setMessages(result.messages);
      onSaved();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>
            Диалоги <span className="count-label">{conversations.length}</span>
          </h2>
          <p>История общения и передача разговора между AI и сотрудником.</p>
        </div>
        <Button variant="secondary" onClick={onSaved}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </div>
      <div className="conversation-workspace panel">
        <aside className="conversation-list">
          {conversations
            .filter((c) =>
              `${c.patient_name} ${c.last_message}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )
            .map((c) => (
              <button
                key={c.id}
                className={selected === c.id ? "active" : ""}
                onClick={() => {
                  setSelected(c.id);
                  setText("");
                }}
              >
                <Avatar name={c.patient_name || "Посетитель"} />
                <div>
                  <strong>{c.patient_name || "Посетитель сайта"}</strong>
                  <p>{c.last_message || "Начат новый диалог"}</p>
                  <span>
                    {c.channel === "telegram" ? (
                      <Send size={12} />
                    ) : (
                      <MessageCircle size={12} />
                    )}{" "}
                    {c.channel === "telegram" ? "Telegram" : "Веб-чат"} ·{" "}
                    {c.mode === "human" ? "Сотрудник" : "AI"}
                  </span>
                </div>
                {c.mode === "human" && <i className="needs-human" />}
              </button>
            ))}
          {!conversations.length && (
            <Empty
              title="Нет диалогов"
              text="Откройте чат на сайте клиники, чтобы начать."
            />
          )}
        </aside>
        <section className="operator-chat">
          {conversation ? (
            <>
              <div className="operator-chat-head">
                <div>
                  <strong>
                    {conversation.patient_name || "Посетитель сайта"}
                  </strong>
                  <Badge
                    tone={conversation.mode === "human" ? "green" : "blue"}
                  >
                    {conversation.mode === "human"
                      ? "Отвечает сотрудник"
                      : "Отвечает AI"}
                  </Badge>
                </div>
                <Button
                  variant={
                    conversation.mode === "human" ? "secondary" : "primary"
                  }
                  loading={busy}
                  onClick={() =>
                    mode(conversation.mode === "human" ? "ai" : "human")
                  }
                >
                  {conversation.mode === "human" ? (
                    <Bot size={16} />
                  ) : (
                    <Headphones size={16} />
                  )}{" "}
                  {conversation.mode === "human"
                    ? "Вернуть AI"
                    : "Забрать диалог"}
                </Button>
              </div>
              <div
                ref={list}
                className="operator-chat-messages"
                aria-live="polite"
              >
                {loading ? (
                  <Loading />
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      className={`chat-bubble ${["user", "patient"].includes(m.role) ? "assistant" : "patient"}`}
                    >
                      <small className="message-role">
                        {["user", "patient"].includes(m.role)
                          ? "Пациент"
                          : m.role === "assistant"
                            ? "Помощник"
                            : "Сотрудник"}
                      </small>
                      <div>{m.text}</div>
                      {m.created_at && <small>{time(m.created_at)}</small>}
                    </div>
                  ))
                )}
              </div>
              <ErrorNote message={error} />
              {conversation.mode === "human" ? (
                <form className="chat-compose operator-compose" onSubmit={send}>
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    maxLength={3000}
                    placeholder="Ответить пациенту…"
                    aria-label="Ответ пациенту"
                  />
                  <button
                    className="send-btn"
                    disabled={busy || !text.trim()}
                    aria-label="Отправить ответ"
                  >
                    <ArrowUp size={21} />
                  </button>
                </form>
              ) : (
                <div className="operator-hint">
                  <Bot size={18} />
                  Сейчас отвечает помощник. Нажмите «Забрать диалог», чтобы
                  написать от своего имени.
                </div>
              )}
            </>
          ) : (
            <Empty
              title="Выберите диалог"
              text="Слева находятся все обращения этой клиники."
            />
          )}
        </section>
      </div>
    </>
  );
}
