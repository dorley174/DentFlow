"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Headphones,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api, errorText, post } from "@/lib/api";
import { ChatOption, ChatState } from "@/lib/types";
import { ErrorNote } from "./ui";
import { time } from "@/lib/format";

export function ChatPanel({
  slug,
  compact = false,
}: {
  slug: string;
  compact?: boolean;
}) {
  const [state, setState] = useState<ChatState>({ messages: [] });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const mutationVersion = useRef(0);
  const sending = useRef(false);
  const route = `/public/clinics/${encodeURIComponent(slug)}/chat`;
  useEffect(() => {
    let active = true;
    const load = async (initial = false) => {
      if (sending.current) return;
      const version = mutationVersion.current;
      try {
        const next = await api<ChatState>(route);
        if (active && version === mutationVersion.current && !sending.current) {
          setState(next);
          if (initial) setError("");
        }
      } catch (e) {
        if (initial && active) setError(errorText(e));
      } finally {
        if (initial && active) setLoading(false);
      }
    };
    load(true);
    const timer = setInterval(() => {
      load();
    }, 12000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [route]);
  useEffect(() => {
    if (listRef.current)
      listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [state.messages.length, busy]);
  async function send(option?: ChatOption) {
    const value = option?.label || text.trim();
    if (!value || busy) return;
    sending.current = true;
    mutationVersion.current += 1;
    setBusy(true);
    setError("");
    try {
      setState(
        await post<ChatState>(route, {
          message: value,
          ...(option ? { action: option.action, data: option.data || {} } : {}),
        }),
      );
      setText("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  const human = state.conversation?.mode === "human";
  return (
    <div className={`chat-panel ${compact ? "chat-compact" : ""}`}>
      <div className="chat-head">
        <span className="chat-agent">
          {human ? <Headphones size={22} /> : <Bot size={23} />}
        </span>
        <div>
          <strong>
            {human ? "Администратор клиники" : "Помощник клиники"}
          </strong>
          <span>
            <i className={`online-dot ${human ? "is-human" : ""}`} />
            {human
              ? "Диалог передан сотруднику"
              : "Помогу выбрать услугу и время"}
          </span>
        </div>
      </div>
      <div
        className="chat-messages"
        ref={listRef}
        aria-live="polite"
        aria-label="История переписки"
      >
        {loading && (
          <div className="chat-bubble assistant">
            <Loader2 size={16} className="spin" /> Подключаемся к клинике…
          </div>
        )}
        {!loading && !state.messages.length && !error && (
          <div className="chat-bubble assistant">
            Здравствуйте! Помогу узнать цены, выбрать врача и записаться. С чего
            начнём?
          </div>
        )}
        {state.messages.map((m, i) => (
          <div
            key={m.id || i}
            className={`chat-bubble ${["user", "patient"].includes(m.role) ? "patient" : "assistant"}`}
          >
            <div>{m.text}</div>
            {m.created_at && <small>{time(m.created_at)}</small>}
          </div>
        ))}
        {busy && (
          <div className="chat-bubble assistant typing">
            <i />
            <i />
            <i />
            <span className="sr-only">Помощник отвечает</span>
          </div>
        )}
      </div>
      <div className="chat-options">
        {state.options?.map((option, i) => (
          <button
            key={`${option.action}-${i}`}
            disabled={busy}
            onClick={() => send(option)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <ErrorNote message={error} />
      <form
        className="chat-compose"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          aria-label="Сообщение помощнику"
          placeholder="Напишите сообщение…"
          value={text}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
          disabled={loading}
        />
        <button
          className="send-btn"
          aria-label="Отправить сообщение"
          disabled={busy || !text.trim() || loading}
        >
          {busy ? (
            <Loader2 size={18} className="spin" />
          ) : (
            <ArrowUp size={21} />
          )}
        </button>
      </form>
      <div className="chat-footer">
        <ShieldCheck size={13} />
        <span>Без диагнозов и медицинских документов</span>
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            send({ label: "Позвать администратора", action: "human", data: {} })
          }
        >
          Позвать человека
        </button>
      </div>
    </div>
  );
}

export function LandingDemo() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Здравствуйте! Я пример цифрового администратора DentFlow. Спросите об услугах, ценах или о том, как работает запись.",
    },
  ]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function send(value: string) {
    if (!value.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await post<{
        reply: string;
        mode: string;
        disclaimer: string;
      }>("/public/demo/chat", { message: value });
      setMessages((m) => [
        ...m,
        { role: "user", text: value },
        { role: "assistant", text: result.reply },
      ]);
      setText("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="landing-demo-chat">
      <div className="chat-head">
        <span className="chat-agent">
          <Sparkles size={22} />
        </span>
        <div>
          <strong>DentFlow Ассистент</strong>
          <span>
            <i className="online-dot" />
            Интерактивный пример
          </span>
        </div>
        <span className="demo-tag">ДЕМО</span>
      </div>
      <div className="chat-messages" aria-live="polite">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`chat-bubble ${m.role === "user" ? "patient" : "assistant"}`}
          >
            {m.text}
          </div>
        ))}
        {busy && (
          <div className="chat-bubble assistant typing">
            <i />
            <i />
            <i />
          </div>
        )}
      </div>
      <div className="chat-options">
        {["Сколько стоит чистка?", "Как записаться?", "Позвать человека"].map(
          (q) => (
            <button key={q} disabled={busy} onClick={() => send(q)}>
              {q}
            </button>
          ),
        )}
      </div>
      <ErrorNote message={error} />
      <form
        className="chat-compose"
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <input
          aria-label="Вопрос в демонстрации"
          placeholder="Попробуйте задать свой вопрос"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={1000}
        />
        <button
          className="send-btn"
          aria-label="Отправить вопрос"
          disabled={busy || !text.trim()}
        >
          <ArrowUp size={20} />
        </button>
      </form>
      <p className="demo-footnote">
        Алгоритмический пример с учебным прайсом. Запись не создаётся,
        персональные данные не вводите.
      </p>
    </div>
  );
}
