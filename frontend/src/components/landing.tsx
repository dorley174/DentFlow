"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Bot,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  GitBranch,
  HeartHandshake,
  LayoutDashboard,
  Menu,
  MessageCircle,
  Play,
  Send,
  ShieldCheck,
  Sparkles,
  UsersRound,
  X,
  Zap,
} from "lucide-react";
import { api, errorText, post } from "@/lib/api";
import { Config } from "@/lib/types";
import { currency } from "@/lib/format";
import { Badge, Button, ErrorNote, Field, Logo } from "./ui";
import { LandingDemo } from "./chat";

const planFeatures: Record<string, string[]> = {
  START: [
    "Онлайн-запись и сайт клиники",
    "Базовая CRM и пациенты",
    "Веб-чат",
    "Один филиал",
  ],
  BUSINESS: [
    "Всё из тарифа Start",
    "AI-администратор и Telegram",
    "Напоминания и задачи",
    "Аналитика обращений",
  ],
  ENTERPRISE: [
    "Несколько филиалов",
    "Индивидуальные настройки",
    "Проектирование интеграций",
    "Расширение под процессы клиники",
  ],
};
const featureTabs = [
  { id: "calendar", title: "Запись", icon: CalendarDays },
  { id: "crm", title: "CRM", icon: GitBranch },
  { id: "chat", title: "Диалоги", icon: MessageCircle },
];

function ProductIllustration({ variant = "calendar" }: { variant?: string }) {
  return (
    <div className="product-illustration">
      <div className="mock-top">
        <span className="mock-logo">
          <Logo compact />
          Smile Avenue
        </span>
        <span className="mock-indicator">
          <i />
          Пример интерфейса
        </span>
      </div>
      <div className="mock-body">
        <div className="mock-sidebar">
          {[
            LayoutDashboard,
            CalendarDays,
            UsersRound,
            MessageCircle,
            GitBranch,
          ].map((Icon, i) => (
            <span
              key={i}
              className={
                i === (variant === "calendar" ? 1 : variant === "crm" ? 4 : 3)
                  ? "active"
                  : ""
              }
            >
              <Icon size={17} />
            </span>
          ))}
        </div>
        <div className="mock-main">
          <div className="mock-heading">
            <div>
              <small>ВАШЕ РАБОЧЕЕ ПРОСТРАНСТВО</small>
              <strong>
                {variant === "calendar"
                  ? "Всё идёт по плану"
                  : variant === "crm"
                    ? "Каждый пациент — на виду"
                    : "В одном диалоге"}
              </strong>
            </div>
            <span className="mock-add">+</span>
          </div>
          {variant === "calendar" ? (
            <>
              <div className="mock-stats">
                <span>
                  <small>ЗАПИСЬ</small>
                  <b>Онлайн</b>
                </span>
                <span>
                  <small>РАСПИСАНИЕ</small>
                  <b>Актуально</b>
                </span>
                <span>
                  <small>ДИАЛОГИ</small>
                  <b>Вместе</b>
                </span>
              </div>
              <div className="mock-calendar">
                <div className="mock-times">
                  <span>09:00</span>
                  <span>10:00</span>
                  <span>11:00</span>
                  <span>12:00</span>
                </div>
                <div className="mock-column">
                  <div className="mock-doctor">
                    <span>АЛ</span>Анна Л.
                  </div>
                  <div className="mock-event green">
                    <small>09:00 – 10:00</small>
                    <strong>Профгигиена</strong>
                    <span>Запись подтверждена</span>
                  </div>
                  <div className="mock-event mint">
                    <small>11:00 – 11:30</small>
                    <strong>Консультация</strong>
                    <span>Онлайн-запись</span>
                  </div>
                </div>
                <div className="mock-column">
                  <div className="mock-doctor">
                    <span>ДМ</span>Дмитрий М.
                  </div>
                  <div className="mock-event blue">
                    <small>10:00 – 11:00</small>
                    <strong>Плановый приём</strong>
                    <span>Администратор</span>
                  </div>
                  <div className="mock-free">
                    <span />
                    Свободное время
                  </div>
                </div>
              </div>
            </>
          ) : variant === "crm" ? (
            <div className="mock-kanban">
              {["Новое обращение", "Предложено время", "Записан"].map(
                (stage, i) => (
                  <div key={stage}>
                    <h4>
                      <i className={`dot-${i}`} />
                      {stage}
                    </h4>
                    {[0, 1].map((n) => (
                      <div className="mock-lead" key={n}>
                        <span>
                          {["МК", "АС", "ЕП", "ДА", "НВ", "ОЛ"][i * 2 + n]}
                        </span>
                        <b>{["Первичный приём", "Профгигиена"][n]}</b>
                        <small>
                          {i === 2 ? "Время подтверждено" : "Диалог сохранён"}
                        </small>
                        <div className="mock-lines">
                          <i />
                          <i />
                        </div>
                      </div>
                    ))}
                  </div>
                ),
              )}
            </div>
          ) : (
            <div className="mock-chat">
              <div className="mock-chat-message patient">
                Добрый вечер! Хочу записаться на чистку.
              </div>
              <div className="mock-chat-message assistant">
                Здравствуйте! Проверим расписание и подберём удобное время.
              </div>
              <div className="mock-chat-message patient">
                Мне удобнее завтра утром.
              </div>
              <div className="mock-chat-action">
                <CalendarDays size={17} />
                <div>
                  <strong>Проверка свободных окон</strong>
                  <small>Цены и время — из данных клиники</small>
                </div>
                <Check size={17} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function Landing() {
  const [config, setConfig] = useState<Config | null>(null);
  const [configError, setConfigError] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const [feature, setFeature] = useState("calendar");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState("");
  useEffect(() => {
    api<Config>("/public/config")
      .then(setConfig)
      .catch((e) => setConfigError(errorText(e)));
  }, []);
  async function requestConnection(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError("");
    const data = new FormData(event.currentTarget);
    try {
      await post("/public/leads", {
        clinic_name: data.get("clinic_name"),
        name: data.get("name"),
        phone: data.get("phone"),
        email: data.get("email"),
        consent: data.get("consent") === "on",
      });
      setSent(true);
    } catch (e) {
      setFormError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="landing-page">
      <header className="landing-nav page-container">
        <Link href="/" aria-label="DentFlow, на главную">
          <Logo />
        </Link>
        <nav className={mobileNav ? "mobile-open" : ""}>
          {[
            ["#features", "Возможности"],
            ["#ai", "AI-администратор"],
            ["#integrations", "Интеграции"],
            ["#pricing", "Тарифы"],
          ].map(([href, label]) => (
            <a key={href} href={href} onClick={() => setMobileNav(false)}>
              {label}
            </a>
          ))}
        </nav>
        <div className="nav-actions">
          <Link className="login-link" href="/login">
            Войти <ArrowUpRight size={14} />
          </Link>
          <a className="btn btn-primary btn-small" href="#connect">
            Подключить клинику
          </a>
          <button
            className="mobile-nav-toggle icon-btn"
            onClick={() => setMobileNav(!mobileNav)}
            aria-label={mobileNav ? "Закрыть меню" : "Открыть меню"}
          >
            {mobileNav ? <X /> : <Menu />}
          </button>
        </div>
      </header>
      <section className="landing-hero page-container">
        <div className="hero-copy">
          <div className="hero-eyebrow">
            <span className="hero-eyebrow-dot" />
            ЕДИНАЯ ПЛАТФОРМА ДЛЯ СТОМАТОЛОГИЙ
          </div>
          <h1>
            Ваша стоматология
            <br />
            работает <em>24/7.</em>
          </h1>
          <h2>Даже когда администратор отдыхает.</h2>
          <p>
            AI-администратор, онлайн-запись и CRM в единой платформе для
            российских стоматологий.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href="#demo">
              Попробовать демо <ArrowRight size={18} />
            </a>
            <a className="btn btn-secondary" href="#connect">
              Подключить клинику
            </a>
          </div>
          <div className="hero-fineprint">
            <ShieldCheck size={15} />
            <span>Ваши процессы. Ваши данные. Одна система.</span>
          </div>
        </div>
        <div className="hero-product">
          <div className="hero-glow" />
          <ProductIllustration />
          <div className="hero-floating-message">
            <span className="sparkle-box">
              <Sparkles size={20} />
            </span>
            <div>
              <strong>Пациент обратился — система подхватила</strong>
              <small>Диалог → запись → CRM → напоминание</small>
            </div>
          </div>
          <div className="hero-floating-badge">
            <CheckCircle2 size={17} />С заботой о каждом обращении
          </div>
        </div>
      </section>
      <div className="value-strip page-container">
        <span>
          Меньше переключений.
          <br />
          <strong>Больше времени для пациентов.</strong>
        </span>
        <div>
          <CalendarDays />
          <span>Онлайн-запись</span>
        </div>
        <div>
          <Bot />
          <span>AI-администратор</span>
        </div>
        <div>
          <GitBranch />
          <span>Единая CRM</span>
        </div>
        <div>
          <MessageCircle />
          <span>Диалоги и задачи</span>
        </div>
      </div>
      <section id="features" className="landing-section page-container">
        <div className="section-heading">
          <div>
            <span className="eyebrow">РАБОЧИЙ ДЕНЬ, КОТОРЫЙ УПРАВЛЯЕТСЯ</span>
            <h2>
              Всё связано.
              <br />
              Ничего не теряется.
            </h2>
          </div>
          <p>
            От первого «Здравствуйте» до следующего визита.
            <br />
            Команда видит одну картину и работает
            <br />с актуальными данными клиники.
          </p>
        </div>
        <div className="feature-workspace">
          <div className="feature-copy">
            <div className="feature-tabs" aria-label="Возможности продукта">
              {featureTabs.map((t) => (
                <button
                  className={feature === t.id ? "active" : ""}
                  key={t.id}
                  onClick={() => setFeature(t.id)}
                >
                  <t.icon size={17} />
                  {t.title}
                </button>
              ))}
            </div>
            <h3>
              {feature === "calendar"
                ? "Расписание без лишних звонков"
                : feature === "crm"
                  ? "Обращение не останется без внимания"
                  : "Помощник и команда работают вместе"}
            </h3>
            <p>
              {feature === "calendar"
                ? "Пациент выбирает услугу, врача и свободное окно. Созданная запись сразу становится частью календаря клиники."
                : feature === "crm"
                  ? "Обращения собираются в воронку. Стадии, ответственные и задачи помогают довести разговор до следующего шага."
                  : "История остаётся в одном месте. Администратор может подключиться к разговору и продолжить его с нужного момента."}
            </p>
            <ul>
              {(feature === "calendar"
                ? [
                    "Проверка свободного времени перед записью",
                    "Переносы, отмены и подтверждения",
                    "День, неделя, месяц и список",
                  ]
                : feature === "crm"
                  ? [
                      "Карточка пациента и история обращений",
                      "Десять понятных стадий воронки",
                      "Задачи и ответственные сотрудники",
                    ]
                  : [
                      "Веб-чат и канал Telegram",
                      "Передача диалога человеку",
                      "Ответы по данным своей клиники",
                    ]
              ).map((x) => (
                <li key={x}>
                  <Check size={16} />
                  {x}
                </li>
              ))}
            </ul>
            <a className="text-link" href="#demo">
              Посмотреть, как это работает <ArrowRight size={17} />
            </a>
          </div>
          <ProductIllustration variant={feature} />
        </div>
        <div className="feature-card-row">
          <article>
            <span>
              <Clock3 size={24} />
            </span>
            <h3>Рутина — по расписанию</h3>
            <p>
              Напоминания о визитах и задачи администраторам запускаются по
              правилам вашей клиники.
            </p>
          </article>
          <article>
            <span>
              <ShieldCheck size={24} />
            </span>
            <h3>Доступ — по роли</h3>
            <p>
              Раздельные пространства клиник, роли сотрудников, журнал операций
              и управление согласиями.
            </p>
          </article>
          <article>
            <span>
              <HeartHandshake size={24} />
            </span>
            <h3>Человек — в нужный момент</h3>
            <p>
              Медицинские вопросы передаются специалисту. Помощник занимается
              организацией визита.
            </p>
          </article>
        </div>
      </section>
      <section id="ai" className="ai-section">
        <div className="page-container ai-layout">
          <div>
            <span className="eyebrow eyebrow-light">
              ЦИФРОВОЙ АДМИНИСТРАТОР
            </span>
            <h2>
              На связи с пациентом.
              <br />
              <em>В контексте клиники.</em>
            </h2>
            <p>
              Помогает узнать цены, выбрать специалиста и найти время. Берёт
              данные из системы, а сложные вопросы передаёт вашей команде.
            </p>
            <div className="ai-points">
              <div>
                <span>01</span>
                <div>
                  <strong>Понимает следующий шаг</strong>
                  <p>Услуга, врач, свободный слот — последовательно.</p>
                </div>
              </div>
              <div>
                <span>02</span>
                <div>
                  <strong>Подтверждает результат</strong>
                  <p>Сообщает о записи после её сохранения в базе.</p>
                </div>
              </div>
              <div>
                <span>03</span>
                <div>
                  <strong>Знает границы</strong>
                  <p>Не ставит диагноз и не назначает лечение.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="ai-architecture">
            <div className="ai-channel-row">
              <span>
                <MessageCircle size={22} />
                Веб-чат
              </span>
              <span>
                <Send size={22} />
                Telegram
              </span>
            </div>
            <div className="architecture-connect" />
            <div className="ai-core">
              <span>
                <Sparkles size={30} />
              </span>
              <strong>DentFlow AI Engine</strong>
              <small>Единая логика обслуживания</small>
            </div>
            <div className="architecture-connect" />
            <div className="ai-tools-row">
              <span>
                <CalendarDays />
                Запись
              </span>
              <span>
                <GitBranch />
                CRM
              </span>
              <span>
                <UsersRound />
                Команда
              </span>
            </div>
            <p>
              Демо-режим работает без ключей.
              <br />
              Внешняя LLM подключается на сервере.
            </p>
          </div>
        </div>
      </section>
      <section
        id="demo"
        className="landing-section page-container demo-section"
      >
        <div className="demo-description">
          <span className="eyebrow">ПОПРОБУЙТЕ САМИ</span>
          <h2>
            Первое знакомство
            <br />
            за один диалог.
          </h2>
          <p>
            Задайте вопрос о стоимости или записи. Этот открытый пример помогает
            понять сценарий общения.
          </p>
          <div className="demo-clarity">
            <CircleHelp size={20} />
            <p>
              Здесь используются учебные данные. Полный сценарий с настоящим
              сохранением записи доступен в тестовой клинике.
            </p>
          </div>
          {config?.dev_tools && (
            <Link href="/clinic/smile-avenue" className="btn btn-secondary">
              Открыть тестовую клинику <ArrowUpRight size={17} />
            </Link>
          )}
          <div className="demo-small-features">
            <span>
              <Check size={15} />
              Без API-ключей
            </span>
            <span>
              <Check size={15} />
              Без медицинских рекомендаций
            </span>
          </div>
        </div>
        <LandingDemo />
      </section>
      <section id="integrations" className="integrations-section">
        <div className="page-container">
          <div className="section-heading">
            <div>
              <span className="eyebrow">ОТКРЫТАЯ АРХИТЕКТУРА</span>
              <h2>
                Встраивается
                <br />в ваш рабочий процесс.
              </h2>
            </div>
            <p>
              Подключения зависят от доступа к системам
              <br />
              клиники. Их статус всегда виден в кабинете.
            </p>
          </div>
          <div className="integration-grid">
            <article>
              <span className="integration-logo telegram">
                <Send size={25} />
              </span>
              <div>
                <h3>Telegram</h3>
                <p>
                  Общий движок с веб-чатом. Для запуска нужен токен собственного
                  бота.
                </p>
                <Badge tone="blue">Адаптер · настройка токена</Badge>
              </div>
            </article>
            <article>
              <span className="integration-logo mis">1C</span>
              <div>
                <h3>Российские МИС</h3>
                <p>
                  Единый интерфейс адаптера. Реальное подключение к 1С —
                  отдельный этап.
                </p>
                <Badge>Подготовлен интеграционный слой</Badge>
              </div>
            </article>
            <article>
              <span className="integration-logo llm">
                <Sparkles size={25} />
              </span>
              <div>
                <h3>Российские AI-провайдеры</h3>
                <p>
                  Сменяемая модель и серверная конфигурация. Демо доступно без
                  внешней LLM.
                </p>
                <Badge>Ключи и проверка подключения</Badge>
              </div>
            </article>
          </div>
        </div>
      </section>
      <section id="pricing" className="landing-section page-container">
        <div className="center-heading">
          <span className="eyebrow">РАСТИТЕ В СВОЁМ ТЕМПЕ</span>
          <h2>Тариф под задачи клиники.</h2>
          <p>
            Пример коммерческой модели. Состав и цены настраиваются владельцем
            платформы.
          </p>
        </div>
        <ErrorNote message={configError} />
        <div className="pricing-grid">
          {config?.plans?.map((plan, i) => {
            const code = String(plan.code).toUpperCase();
            return (
              <article
                className={`price-card ${code === "BUSINESS" ? "featured" : ""}`}
                key={plan.code}
              >
                {code === "BUSINESS" && (
                  <span className="price-recommend">
                    <Sparkles size={13} />
                    Для работы с AI
                  </span>
                )}
                <span className="plan-code">{code}</span>
                <h3>{plan.name || ["Старт", "Бизнес", "Индивидуально"][i]}</h3>
                <div className="price-value">
                  {plan.price_kopecks
                    ? currency(plan.price_kopecks)
                    : "По запросу"}
                  {Boolean(plan.price_kopecks) && <span>/ месяц</span>}
                </div>
                <a
                  href="#connect"
                  className={`btn btn-${code === "BUSINESS" ? "primary" : "secondary"}`}
                >
                  Обсудить подключение
                  <ArrowRight size={16} />
                </a>
                <ul>
                  {(plan.features || planFeatures[code] || []).map((f) => (
                    <li key={f}>
                      <Check size={16} />
                      {f}
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
        <p className="pricing-note">
          <ShieldCheck size={14} />
          На тестовом стенде оплата имитируется. Списаний нет.
        </p>
      </section>
      <section className="page-container faq-section">
        <div>
          <span className="eyebrow">ЕСТЬ ВОПРОСЫ?</span>
          <h2>Давайте разберёмся.</h2>
          <p>
            Несколько вещей, которые полезно
            <br />
            знать перед началом.
          </p>
        </div>
        <div className="faq-list">
          {[
            [
              "Можно попробовать до подключения реальной клиники?",
              "Да. В отдельном тестовом стенде есть Smile Avenue с учебными врачами, пациентами и расписанием. Запись на сайте, диалог и кабинет администратора работают с одной тестовой базой.",
            ],
            [
              "AI заменяет администратора?",
              "Он помогает с административными вопросами и организацией записи. Сотрудник сохраняет контроль, видит историю и может забрать диалог себе. Медицинские рекомендации остаются задачей специалиста.",
            ],
            [
              "Что нужно для Telegram?",
              "Свой бот, токен от BotFather и настроенный сервер. Инструкция есть в проекте. Доступ к реальному Telegram проверяется после добавления вашего токена.",
            ],
            [
              "У нас уже есть медицинская информационная система. Что делать?",
              "В проекте предусмотрен интеграционный слой с демонстрационным адаптером. Для реальной МИС отдельно проверяются доступ, лицензии, API и синхронизация. Наличие логотипа МИС не означает готовое подключение.",
            ],
            [
              "Где размещать данные?",
              "Production рассчитан на отдельную инфраструктуру в России. Размещение, договоры, согласия и меры защиты нужно проверить перед использованием реальных данных. Технический проект не заменяет юридическую оценку.",
            ],
          ].map(([q, a]) => (
            <details key={q}>
              <summary>
                {q}
                <ChevronDown size={18} />
              </summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>
      <section id="connect" className="connect-section page-container">
        <div>
          <span className="eyebrow">НАЧНЁМ С ВАШЕЙ КЛИНИКИ</span>
          <h2>
            Больше заботы.
            <br />
            <em>Меньше рутины.</em>
          </h2>
          <p>
            Оставьте заявку на подключение. Она сохранится в панели владельца
            платформы.
          </p>
          <div className="connect-steps">
            <span>
              <i>1</i>Знакомство с процессами
            </span>
            <span>
              <i>2</i>Настройка тестового контура
            </span>
            <span>
              <i>3</i>Проверка и запуск
            </span>
          </div>
        </div>
        <div className="connection-form">
          {sent ? (
            <div className="form-success">
              <CheckCircle2 size={42} />
              <h3>Заявка сохранена</h3>
              <p>
                Владелец платформы увидит её в панели управления. Спасибо за
                интерес к DentFlow.
              </p>
              <Button variant="secondary" onClick={() => setSent(false)}>
                Отправить ещё одну
              </Button>
            </div>
          ) : (
            <form onSubmit={requestConnection}>
              <h3>Обсудим вашу задачу</h3>
              <Field label="Название клиники">
                <input
                  name="clinic_name"
                  required
                  placeholder="Например, Стоматология Улыбка"
                  maxLength={200}
                />
              </Field>
              <div className="form-grid">
                <Field label="Ваше имя">
                  <input
                    name="name"
                    required
                    placeholder="Как к вам обращаться"
                    minLength={2}
                    maxLength={100}
                  />
                </Field>
                <Field label="Телефон">
                  <input
                    name="phone"
                    type="tel"
                    required
                    placeholder="+7 (999) 123-45-67"
                    minLength={10}
                    maxLength={30}
                  />
                </Field>
              </div>
              <Field label="Рабочий email">
                <input
                  name="email"
                  type="email"
                  required
                  placeholder="name@clinic.ru"
                  maxLength={200}
                />
              </Field>
              <label className="checkbox-field">
                <input name="consent" type="checkbox" required />
                <span>
                  Согласен на обработку контактных данных для ответа на заявку.{" "}
                  <Link href="/privacy">Условия</Link>
                </span>
              </label>
              <ErrorNote message={formError} />
              <Button type="submit" loading={busy}>
                Отправить заявку
                <ArrowRight size={17} />
              </Button>
            </form>
          )}
        </div>
      </section>
      <footer className="landing-footer page-container">
        <div>
          <Link href="/">
            <Logo />
          </Link>
          <p>Единая платформа заботы о пациентах.</p>
        </div>
        <nav>
          <a href="#features">Возможности</a>
          <a href="#demo">Демо</a>
          <a href="#pricing">Тарифы</a>
          <Link href="/login">Вход в кабинет</Link>
        </nav>
        <div className="footer-bottom">
          <span>© {new Date().getFullYear()} DentFlow</span>
          <Link href="/privacy">Обработка персональных данных</Link>
          <span>Создано для российских клиник</span>
        </div>
      </footer>
    </main>
  );
}
