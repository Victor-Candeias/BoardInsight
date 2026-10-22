// Formatação PT-PT; datas guardadas em UTC e apresentadas em Europe/Lisbon (metrics-definitions).
const LOCALE = "pt-PT";
const TIME_ZONE = "Europe/Lisbon";
const EMPTY = "—";
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

type Value = string | number | Date | null | undefined;

const dateFormat = new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: TIME_ZONE });
// Datas sem hora ("2026-10-01") são dias de calendário: não converter de fuso.
const dayFormat = new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });
const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: TIME_ZONE,
});
const numberFormats = new Map<number, Intl.NumberFormat>();

function toDate(value: Value): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: Value): string {
  const date = toDate(value);
  if (!date) return EMPTY;
  return (typeof value === "string" && DATE_ONLY.test(value) ? dayFormat : dateFormat).format(date);
}

export function formatDateTime(value: Value): string {
  const date = toDate(value);
  return date ? dateTimeFormat.format(date) : EMPTY;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return EMPTY;
  let format = numberFormats.get(digits);
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 0, maximumFractionDigits: digits });
    numberFormats.set(digits, format);
  }
  return format.format(value);
}

export function formatDays(value: number | null | undefined): string {
  const text = formatNumber(value, 1);
  return text === EMPTY ? EMPTY : `${text} d`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return EMPTY;
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return "< 1 min";
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  if (days > 0) return hours ? `${days} d ${hours} h` : `${days} d`;
  if (hours > 0) return mins ? `${hours} h ${mins} min` : `${hours} h`;
  return `${mins} min`;
}
