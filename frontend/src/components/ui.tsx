"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import {
  X,
  Check,
  AlertCircle,
  Loader2,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import { initials, statuses } from "@/lib/format";

export function Logo({
  light = false,
  compact = false,
}: {
  light?: boolean;
  compact?: boolean;
}) {
  return (
    <span className={`logo ${light ? "logo-light" : ""}`}>
      <span className="logo-mark" aria-hidden="true">
        <svg viewBox="0 0 40 40">
          <path
            d="M8 9h10c9 0 15 4 15 11S27 31 18 31H8V9Zm7 6v10h4c5 0 7-2 7-5s-2-5-7-5h-4Z"
            fill="currentColor"
          />
          <path d="M7 17h14v6H7z" fill="#9ee8d2" />
        </svg>
      </span>
      {!compact && (
        <span>
          Dent<span className="logo-flow">Flow</span>
          <span className="logo-dot">.</span>
        </span>
      )}
    </span>
  );
}
export function Button({
  children,
  variant = "primary",
  loading = false,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: string;
  loading?: boolean;
}) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={`btn btn-${variant} ${className}`}
    >
      {loading && <Loader2 size={16} className="spin" />}
      {children}
    </button>
  );
}
export function Badge({
  children,
  tone = "neutral",
  dot = false,
}: {
  children: ReactNode;
  tone?: string;
  dot?: boolean;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      {dot && <span className="badge-dot" />}
      {children}
    </span>
  );
}
export function Status({ value }: { value: string }) {
  const tone = ["confirmed", "completed", "done", "active", "sent"].includes(
    value,
  )
    ? "green"
    : ["cancelled", "failed", "blocked", "no_show"].includes(value)
      ? "red"
      : ["scheduled", "in_progress", "ai"].includes(value)
        ? "blue"
        : "neutral";
  return (
    <Badge tone={tone} dot>
      {statuses[value] || value}
    </Badge>
  );
}
export function Avatar({
  name,
  color,
  small = false,
}: {
  name: string;
  color?: string;
  small?: boolean;
}) {
  return (
    <span
      className={`avatar ${small ? "avatar-small" : ""}`}
      style={color ? { background: `${color}18`, color } : undefined}
    >
      {initials(name)}
    </span>
  );
}
export function Field({
  label,
  hint,
  children,
  className = "",
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`field ${className}`}>
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function ErrorNote({ message }: { message?: string }) {
  return message ? (
    <div className="error-note" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Empty({
  title = "Здесь пока ничего нет",
  text = "Новые данные появятся в этом разделе.",
  children,
}: {
  title?: string;
  text?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-symbol">
        <Sparkles size={22} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {children}
    </div>
  );
}
export function Loading({ text = "Загружаем данные…" }: { text?: string }) {
  return (
    <div className="loading-state">
      <Loader2 className="spin" size={24} />
      <span>{text}</span>
    </div>
  );
}
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    else if (!open && d.open) d.close();
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`modal ${wide ? "modal-wide" : ""}`}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-label={title}
    >
      <div className="modal-head">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        <button
          type="button"
          className="icon-btn"
          onClick={onClose}
          aria-label="Закрыть"
        >
          <X size={20} />
        </button>
      </div>
      <div className="modal-body">{open && children}</div>
    </dialog>
  );
}

const ToastContext = createContext<
  (message: string, kind?: "success" | "error") => void
>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<
    { id: number; message: string; kind: "success" | "error" }[]
  >([]);
  const notify = useCallback(
    (message: string, kind: "success" | "error" = "success") => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t, { id, message, kind }]);
      setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
    },
    [],
  );
  return (
    <ToastContext.Provider value={notify}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((t) => (
          <div className={`toast ${t.kind}`} key={t.id}>
            {t.kind === "success" ? (
              <Check size={19} />
            ) : (
              <AlertCircle size={19} />
            )}
            <span>{t.message}</span>
            <button
              aria-label="Закрыть уведомление"
              onClick={() => setToasts((x) => x.filter((v) => v.id !== t.id))}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
export function ExternalMark() {
  return <ArrowUpRight size={15} />;
}
