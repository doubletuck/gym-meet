import type { Athlete } from "~/api/types";

/** A total or E score, to the three decimals results are published to: 14.566, 14.000. */
export function formatScore(value: number | null | undefined): string {
  return value == null ? "" : value.toFixed(3);
}

/**
 * A D score, bonus or penalty, as written: 6.3, 5.7, 0.05. Results books print
 * these with as few decimals as they need, so trailing zeros aren't added.
 */
export function formatValue(value: number | null | undefined): string {
  if (value == null) {
    return "";
  }
  return Number.isInteger(value) ? value.toFixed(1) : String(value);
}

export function athleteName(athlete: Athlete): string {
  return `${athlete.givenName} ${athlete.surname}`;
}

// API dates are calendar days ("2026-10-17"); read and printed in UTC so no time zone shifts the day
function parseDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date));
}

const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const WEEKDAY = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });

/** "17 – 25 Oct 2026" */
export function formatDateRange(start: string, end: string): string {
  return DAY.formatRange(parseDay(start), parseDay(end));
}

/** "Sat 17 Oct", or for a session held over several days, "Thu 6 Aug – Sat 8 Aug" */
export function formatSessionDate(day: string, endDay?: string | null): string {
  return endDay ? WEEKDAY.formatRange(parseDay(day), parseDay(endDay)) : WEEKDAY.format(parseDay(day));
}
