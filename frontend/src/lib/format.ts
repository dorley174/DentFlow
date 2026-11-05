export const currency = (kopecks = 0) =>
  new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: kopecks % 100 ? 2 : 0,
  }).format(Number(kopecks) / 100);
export const shortNumber = (number = 0) =>
  new Intl.NumberFormat("ru-RU").format(number);
export const dayKey = (date: string | Date = new Date()) =>
  new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(date));
export const time = (date: string) =>
  date
    ? new Intl.DateTimeFormat("ru-RU", {
        timeZone: "Europe/Moscow",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(date))
    : "—";
export const dateLabel = (
  date: string | Date,
  options: Intl.DateTimeFormatOptions = {},
) =>
  new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    day: "numeric",
    month: "long",
    ...options,
  }).format(new Date(date));
export function addDays(date: string, count: number) {
  const d = new Date(`${date}T12:00:00+03:00`);
  d.setUTCDate(d.getUTCDate() + count);
  return dayKey(d);
}
export const initials = (name = "") =>
  name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();
export const roles: Record<string, string> = {
  super_admin: "Владелец платформы",
  owner: "Владелец клиники",
  manager: "Управляющий",
  administrator: "Администратор",
  doctor: "Врач",
  patient: "Пациент",
};
export const statuses: Record<string, string> = {
  scheduled: "Записан",
  confirmed: "Подтверждён",
  completed: "Завершён",
  cancelled: "Отменён",
  no_show: "Не пришёл",
  open: "Открыта",
  in_progress: "В работе",
  done: "Готово",
  active: "Активен",
  blocked: "Заблокирован",
  pending: "В очереди",
  sent: "Доставлено",
  failed: "Ошибка",
  human: "Сотрудник",
  ai: "AI",
  demo: "Демо",
  unconfigured: "Не настроено",
  not_configured: "Не настроено",
  configured: "Настроено",
  disabled: "Отключено",
  draft: "Черновик",
  connected: "Подключено",
  not_connected: "Не подключено",
  planned: "Запланировано",
  delivered: "Доставлено",
  processed: "Обработано",
};
export const stages = [
  "Новое обращение",
  "Не обработано",
  "В работе",
  "Консультация",
  "Предложено время",
  "Записан",
  "Подтверждён",
  "Посетил",
  "Завершено",
  "Потерян",
];
