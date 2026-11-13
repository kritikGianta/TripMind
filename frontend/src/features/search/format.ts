import type { Schemas } from "@/lib/api/client";

export type Money = Schemas["MoneyOut"];

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(currency: string, whole: boolean) {
  const key = `${currency}:${whole}`;
  let fmt = formatters.get(key);
  if (!fmt) {
    fmt = new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      ...(whole ? { maximumFractionDigits: 0, minimumFractionDigits: 0 } : {}),
    });
    formatters.set(key, fmt);
  }
  return fmt;
}

/** Minor units -> "₹4,999". Whole units unless the amount has a fractional part. */
export function formatMoney(money: Money | null | undefined): string {
  if (!money) return "—";
  const digits = formatter(money.currency, false).resolvedOptions().maximumFractionDigits ?? 2;
  const major = money.amount_minor / 10 ** digits;
  return formatter(money.currency, Number.isInteger(major)).format(major);
}

export function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h ${m.toString().padStart(2, "0")}m` : `${m}m`;
}

/** Local wall-clock times arrive as "2026-11-13T06:05:00": show them as written, no tz shift. */
export function clockTime(local: string): string {
  return local.slice(11, 16);
}

const dayFormat = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });

export function formatDay(isoDate: string): string {
  return dayFormat.format(new Date(`${isoDate.slice(0, 10)}T00:00:00`));
}

/** Calendar days between two local times ("+1" when a flight lands the next day). */
export function dayOffset(fromLocal: string, toLocal: string): number {
  const a = Date.parse(`${fromLocal.slice(0, 10)}T00:00:00Z`);
  const b = Date.parse(`${toLocal.slice(0, 10)}T00:00:00Z`);
  return Math.round((b - a) / 86_400_000);
}

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** Today in the traveller's own timezone (the data has flights and rooms from today onwards). */
export function todayIso(): string {
  const now = new Date();
  const today = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  return today;
}

export const CABIN_LABELS: Record<string, string> = {
  economy: "Economy",
  premium_economy: "Premium economy",
  business: "Business",
  first: "First",
};

export const BOARD_LABELS: Record<string, string> = {
  room_only: "Room only",
  breakfast: "Breakfast included",
  half_board: "Half board",
  full_board: "Full board",
  all_inclusive: "All inclusive",
};
