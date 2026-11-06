import type { BookingStatus } from "./types";

export const TZ = "Asia/Bishkek";

/** ISO-время → дата YYYY-MM-DD по Бишкеку. */
export function localDate(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

export function todayISO(): string {
  return localDate(new Date().toISOString());
}

/** Сдвиг даты YYYY-MM-DD на n дней (календарно, без часовых поясов). */
export function addDays(day: string, n: number): string {
  const [y, m, d] = day.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + n));
  return dt.toISOString().slice(0, 10);
}

export function daysBetween(a: string, b: string): number {
  const toUtc = (s: string) => {
    const [y, m, d] = s.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((toUtc(b) - toUtc(a)) / 86400000);
}

export function weekday(day: string): number {
  const [y, m, d] = day.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7; // 0 = пн
}

export const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
  "октября", "ноября", "декабря"];
export const MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь",
  "Октябрь", "Ноябрь", "Декабрь"];

export function fmtDay(day: string): string {
  const [, m, d] = day.split("-").map(Number);
  return `${d} ${MONTHS_GEN[m - 1]}`;
}

export function fmtDateTime(iso: string): string {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, day: "numeric", month: "long", hour: "2-digit",
    minute: "2-digit" }).format(new Date(iso));
}

export function fmtTime(t: string): string {
  return t.slice(0, 5);
}

export function money(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "number" ? v : Number(v);
  return `${Math.round(n).toLocaleString("ru-RU").replace(/,/g, " ")} сом`;
}

export function nightsWord(n: number): string {
  const n10 = n % 10, n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return "ночь";
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return "ночи";
  return "ночей";
}

export const STATUS: Record<BookingStatus, { label: string; cls: string }> = {
  awaiting_payment: { label: "Ждёт оплаты", cls: "st-wait" },
  awaiting_confirmation: { label: "Чек на проверке", cls: "st-check" },
  confirmed: { label: "Подтверждена", cls: "st-ok" },
  checked_in: { label: "Гость живёт", cls: "st-in" },
  checked_out: { label: "Выехал", cls: "st-out" },
  closed: { label: "Закрыта", cls: "st-closed" },
  cancelled: { label: "Отменена", cls: "st-cancel" },
  expired: { label: "Не оплачена", cls: "st-cancel" },
  blocked: { label: "Заблокировано", cls: "st-block" },
};

export const SOURCES: Record<string, string> = {
  lalafo: "Lalafo",
  instagram: "Instagram",
  direct: "Прямой заход",
  manual: "Вручную",
  other: "Другое",
};

export const EXPENSE_CATEGORIES: Record<string, string> = {
  cleaning: "Уборка",
  utilities: "Коммуналка",
  repair: "Ремонт",
  supplies: "Расходники",
  other: "Прочее",
};

/** Ночь `day` занята диапазоном [start, end) из API? */
export function nightBusy(day: string, ranges: { start_at: string; end_at: string }[]): boolean {
  return ranges.some((r) => localDate(r.start_at) <= day && day < localDate(r.end_at));
}

export function sourceFromUrl(): string {
  const src = new URLSearchParams(window.location.search).get("src");
  return src ? src.toLowerCase() : "direct";
}
