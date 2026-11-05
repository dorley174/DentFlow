"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Eye,
  EyeOff,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api, errorText, post } from "@/lib/api";
import { Config, User } from "@/lib/types";
import { Button, ErrorNote, Field, Logo } from "./ui";

export function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [config, setConfig] = useState<Config | null>(null);
  useEffect(() => {
    api<Config>("/public/config")
      .then(setConfig)
      .catch(() => {});
  }, []);
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await post<{ user: User }>("/auth/login", {
        email: email.trim(),
        password,
      });
      router.push(
        result.user.role === "super_admin"
          ? "/super"
          : result.user.role === "patient"
            ? "/clinic/smile-avenue"
            : "/admin",
      );
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Link href="/">
          <Logo light />
        </Link>
        <div>
          <span className="eyebrow eyebrow-light">
            ВАШ СПОКОЙНЫЙ РАБОЧИЙ ДЕНЬ
          </span>
          <h1>
            Забота о пациентах.
            <br />
            <em>Порядок в процессах.</em>
          </h1>
          <p>
            Расписание, диалоги и команда в одном пространстве. Добро пожаловать
            в DentFlow.
          </p>
          <div className="login-quote">
            <Sparkles size={25} />
            <div>
              <strong>От обращения — к визиту</strong>
              <span>Все шаги сохраняются в вашей системе.</span>
            </div>
          </div>
        </div>
        <span className="login-bottom">
          <ShieldCheck size={16} />
          Доступ к данным определяется вашей ролью.
        </span>
      </section>
      <section className="login-form-side">
        <Link href="/" className="text-link">
          <ArrowLeft size={16} />
          На главную
        </Link>
        <div className="login-form-wrap">
          <span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span>
          <h2>Рады вас видеть</h2>
          <p>Введите данные учётной записи.</p>
          <form onSubmit={login}>
            <Field label="Email">
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@clinic.ru"
              />
            </Field>
            <Field label="Пароль">
              <span className="password-field">
                <input
                  type={show ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Ваш пароль"
                />
                <button
                  type="button"
                  aria-label={show ? "Скрыть пароль" : "Показать пароль"}
                  onClick={() => setShow(!show)}
                >
                  {show ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </span>
            </Field>
            <ErrorNote message={error} />
            <Button type="submit" loading={busy}>
              Войти в кабинет <ArrowRight size={17} />
            </Button>
          </form>
          {config?.dev_tools && (
            <div className="demo-login">
              <span>
                <i />
                Тестовый стенд
              </span>
              <p>
                Выберите тестовую роль, затем нажмите «Войти». Данные вымышлены.
              </p>
              <div>
                {[
                  ["admin", "Администратор", "Admin"],
                  ["owner", "Владелец клиники", "Owner"],
                  ["manager", "Управляющий", "Manager"],
                  ["doctor", "Врач", "Doctor"],
                  ["patient", "Пациент", "Patient"],
                  ["super", "Владелец платформы", "Super"],
                ].map(([key, label, prefix]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      setEmail(`${key}@dentflow.local`);
                      setPassword(`${prefix}-Demo-2026!`);
                      setError("");
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}
          <p className="login-help">
            Доступ выдаёт владелец клиники. Если забыли пароль, обратитесь к
            нему для смены данных входа.
          </p>
        </div>
      </section>
    </main>
  );
}
