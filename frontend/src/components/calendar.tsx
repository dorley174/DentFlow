"use client";
import { useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Clock3,
  SlidersHorizontal,
} from "lucide-react";
import { Appointment, Branch, Doctor } from "@/lib/types";
import { addDays, dateLabel, dayKey, time } from "@/lib/format";
import { Avatar, Button, Empty, Status } from "./ui";

export function AppointmentTable({
  appointments,
  onSelect,
}: {
  appointments: Appointment[];
  onSelect: (a: Appointment) => void;
}) {
  if (!appointments.length)
    return (
      <Empty
        title="Записей пока нет"
        text="Новая запись появится здесь после сохранения."
      />
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Дата и время</th>
            <th>Пациент</th>
            <th>Услуга и врач</th>
            <th>Филиал</th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {[...appointments]
            .sort((a, b) => a.start_at.localeCompare(b.start_at))
            .map((a) => (
              <tr key={a.id}>
                <td>
                  <strong>{time(a.start_at)}</strong>
                  <small>{dateLabel(a.start_at, { month: "short" })}</small>
                </td>
                <td>
                  <div className="cell-person">
                    <Avatar name={a.patient_name} small />
                    <strong>{a.patient_name}</strong>
                  </div>
                </td>
                <td>
                  <strong>{a.service_name}</strong>
                  <small>{a.doctor_name}</small>
                </td>
                <td>{a.branch_name}</td>
                <td>
                  <Status value={a.status} />
                </td>
                <td className="table-actions">
                  <button className="text-btn" onClick={() => onSelect(a)}>
                    Открыть
                  </button>
                </td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

export function Calendar({
  appointments,
  doctors,
  branches,
  onSelect,
  onSchedules,
  canManage,
}: {
  appointments: Appointment[];
  doctors: Doctor[];
  branches: Branch[];
  onSelect: (a: Appointment) => void;
  onSchedules: () => void;
  canManage: boolean;
}) {
  const [date, setDate] = useState(dayKey());
  const [view, setView] = useState("day");
  const [doctor, setDoctor] = useState("");
  const [branch, setBranch] = useState("");
  const visible = appointments.filter(
    (a) =>
      a.status !== "cancelled" &&
      (!doctor || a.doctor_id === doctor) &&
      (!branch || a.branch_id === branch),
  );
  const visibleDoctors = doctors.filter(
    (d) =>
      d.active &&
      (!doctor || d.id === doctor) &&
      (!branch || d.branch_id === branch),
  );
  const monday = useMemo(() => {
    const dow = new Date(`${date}T12:00:00+03:00`).getUTCDay();
    return addDays(date, -(dow === 0 ? 6 : dow - 1));
  }, [date]);
  function move(delta: number) {
    if (view === "month") {
      const d = new Date(`${date}T12:00:00+03:00`);
      d.setUTCDate(1);
      d.setUTCMonth(d.getUTCMonth() + delta);
      setDate(dayKey(d));
    } else
      setDate(
        addDays(date, delta * (view === "week" || view === "list" ? 7 : 1)),
      );
  }
  const monthFirst = `${date.slice(0, 7)}-01`;
  const monthDow = new Date(`${monthFirst}T12:00:00+03:00`).getUTCDay();
  const gridFirst = addDays(monthFirst, -(monthDow === 0 ? 6 : monthDow - 1));
  return (
    <div className="panel calendar-panel">
      <div className="calendar-toolbar">
        <div className="calendar-date-control">
          <button
            className="icon-btn"
            aria-label="Предыдущий период"
            onClick={() => move(-1)}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            className="icon-btn"
            aria-label="Следующий период"
            onClick={() => move(1)}
          >
            <ChevronRight size={18} />
          </button>
          <input
            type="date"
            aria-label="Дата календаря"
            value={date}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
          <button className="text-btn" onClick={() => setDate(dayKey())}>
            Сегодня
          </button>
        </div>
        <div className="segmented">
          {[
            ["day", "День"],
            ["week", "Неделя"],
            ["month", "Месяц"],
            ["list", "Список"],
          ].map(([id, title]) => (
            <button
              className={view === id ? "active" : ""}
              onClick={() => setView(id)}
              key={id}
            >
              {title}
            </button>
          ))}
        </div>
      </div>
      <div className="calendar-filters">
        <select
          aria-label="Врач в календаре"
          value={doctor}
          onChange={(e) => setDoctor(e.target.value)}
        >
          <option value="">Все врачи</option>
          {doctors.map((d) => (
            <option value={d.id} key={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Филиал в календаре"
          value={branch}
          onChange={(e) => {
            setBranch(e.target.value);
            setDoctor("");
          }}
        >
          <option value="">Все филиалы</option>
          {branches.map((b) => (
            <option value={b.id} key={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <span>
          <Clock3 size={14} />
          Время по Москве
        </span>
        {canManage && (
          <Button variant="ghost" onClick={onSchedules}>
            <SlidersHorizontal size={16} />
            Рабочие часы
          </Button>
        )}
      </div>
      {view === "day" && (
        <div className="calendar-scroll">
          <div
            className="day-calendar"
            style={{
              gridTemplateColumns: `58px repeat(${Math.max(visibleDoctors.length, 1)}, minmax(155px, 1fr))`,
            }}
          >
            <div className="day-time-heading">МСК</div>
            {visibleDoctors.map((d) => (
              <div className="day-doctor-heading" key={d.id}>
                <Avatar name={d.name} color={d.color} small />
                <div>
                  <strong>{d.name}</strong>
                  <small>{d.specialty}</small>
                </div>
              </div>
            ))}
            <div className="time-rail">
              {Array.from({ length: 13 }, (_, i) => (
                <span key={i}>{String(i + 8).padStart(2, "0")}:00</span>
              ))}
            </div>
            {visibleDoctors.map((d) => (
              <div className="day-doctor-column" key={d.id}>
                {Array.from({ length: 13 }, (_, i) => (
                  <div className="calendar-hour" key={i} />
                ))}
                {visible
                  .filter(
                    (a) => a.doctor_id === d.id && dayKey(a.start_at) === date,
                  )
                  .map((a) => {
                    const [hours, minutes] = time(a.start_at)
                      .split(":")
                      .map(Number);
                    const duration =
                      (new Date(a.end_at).getTime() -
                        new Date(a.start_at).getTime()) /
                      60000;
                    return (
                      <button
                        className={`calendar-event event-${a.status}`}
                        style={{
                          top: `${Math.max(0, (hours - 8) * 64 + (minutes * 64) / 60)}px`,
                          height: `${Math.max(35, (duration * 64) / 60 - 3)}px`,
                          borderLeftColor: d.color || "#087f8c",
                        }}
                        key={a.id}
                        onClick={() => onSelect(a)}
                      >
                        <small>
                          {time(a.start_at)}–{time(a.end_at)}
                        </small>
                        <strong>{a.patient_name}</strong>
                        <span>{a.service_name}</span>
                      </button>
                    );
                  })}
              </div>
            ))}
          </div>
          {!visibleDoctors.length && (
            <Empty
              title="Нет врачей в выбранном фильтре"
              text="Выберите другой филиал или добавьте врача."
            />
          )}
        </div>
      )}
      {view === "week" && (
        <div className="week-calendar">
          {Array.from({ length: 7 }, (_, i) => {
            const day = addDays(monday, i);
            const daily = visible.filter((a) => dayKey(a.start_at) === day);
            return (
              <div key={day} className={day === dayKey() ? "today" : ""}>
                <button
                  className="week-day-head"
                  onClick={() => {
                    setDate(day);
                    setView("day");
                  }}
                >
                  <span>
                    {dateLabel(day, {
                      weekday: "short",
                      day: undefined,
                      month: undefined,
                    })}
                  </span>
                  <strong>{new Date(day).getUTCDate()}</strong>
                </button>
                <div className="week-events">
                  {daily.map((a) => (
                    <button
                      key={a.id}
                      className={`calendar-event event-${a.status}`}
                      onClick={() => onSelect(a)}
                    >
                      <small>{time(a.start_at)}</small>
                      <strong>{a.patient_name}</strong>
                      <span>{a.doctor_name}</span>
                    </button>
                  ))}
                  {!daily.length && (
                    <span className="week-empty">Нет записей</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {view === "month" && (
        <div className="month-calendar">
          <div className="month-weekdays">
            {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((w) => (
              <span key={w}>{w}</span>
            ))}
          </div>
          <div className="month-grid">
            {Array.from({ length: 42 }, (_, i) => {
              const day = addDays(gridFirst, i);
              const daily = visible.filter((a) => dayKey(a.start_at) === day);
              return (
                <button
                  className={`${day.slice(0, 7) !== date.slice(0, 7) ? "outside-month" : ""} ${day === dayKey() ? "today" : ""}`}
                  key={day}
                  onClick={() => {
                    setDate(day);
                    setView("day");
                  }}
                >
                  <strong>{new Date(day).getUTCDate()}</strong>
                  {daily.slice(0, 2).map((a) => (
                    <span key={a.id}>
                      {time(a.start_at)} {a.patient_name}
                    </span>
                  ))}
                  {daily.length > 2 && <small>Ещё {daily.length - 2}</small>}
                </button>
              );
            })}
          </div>
        </div>
      )}
      {view === "list" && (
        <>
          <div className="list-period">
            {dateLabel(date)} — {dateLabel(addDays(date, 6))}
          </div>
          <AppointmentTable
            appointments={visible.filter(
              (a) =>
                dayKey(a.start_at) >= date &&
                dayKey(a.start_at) <= addDays(date, 6),
            )}
            onSelect={onSelect}
          />
        </>
      )}
    </div>
  );
}
