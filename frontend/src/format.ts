import type { EventCard, Occurrence } from "./types";

type Dated = Pick<Occurrence, "start_date" | "end_date" | "date_status">;
type Priced = Pick<Occurrence, "price_min" | "price_max">;

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Dates arrive as "YYYY-MM-DD"; parse them as local dates, not UTC midnight.
export function parseDate(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function monthName(month: number): string {
  return MONTHS[month - 1] ?? "";
}

export function formatDates(occurrence: Dated): string {
  const start = parseDate(occurrence.start_date);
  if (occurrence.date_status === "estimated") {
    return `Est. ${MONTHS[start.getMonth()]} ${start.getFullYear()}`;
  }

  const short = (d: Date) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const weekday = (d: Date) => d.toLocaleDateString(undefined, { weekday: "short" });
  if (!occurrence.end_date || occurrence.end_date === occurrence.start_date) {
    return `${weekday(start)}, ${short(start)}, ${start.getFullYear()}`;
  }

  const end = parseDate(occurrence.end_date);
  if (start.getFullYear() === end.getFullYear()) {
    if (start.getMonth() === end.getMonth()) {
      return `${short(start)}–${end.getDate()}, ${start.getFullYear()}`;
    }
    return `${short(start)} – ${short(end)}, ${start.getFullYear()}`;
  }
  return `${short(start)}, ${start.getFullYear()} – ${short(end)}, ${end.getFullYear()}`;
}

/** The date line for a card: real dates, an estimate, or the usual month. */
export function whenLabel(event: EventCard): string {
  if (event.next) return formatDates(event.next);
  if (event.expected_month) return `Usually in ${monthName(event.expected_month)}`;
  if (!event.active) return "No longer running";
  return "Dates unknown";
}

export function formatPrice(occurrence: Priced | null): string {
  if (!occurrence) return "Price unknown";
  const { price_min: min, price_max: max } = occurrence;
  const money = (n: number) => (Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`);

  if (min === null && max === null) return "Price TBA";
  if (min === 0 && (max === null || max === 0)) return "Free";
  if (min !== null && max !== null && max !== min) {
    return `${min === 0 ? "Free" : money(min)}–${money(max)}`;
  }
  return money((min ?? max) as number);
}

export function formatDrive(minutes: number | null): string {
  if (minutes === null) return "Drive time unknown";
  if (minutes < 60) return `~${minutes} min drive`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const rounded = Math.round(rest / 5) * 5;
  return rounded === 0 || rounded === 60
    ? `~${hours + (rounded === 60 ? 1 : 0)} hr drive`
    : `~${hours} hr ${rounded} min drive`;
}

export function formatHours(minutes: number): string {
  const hours = minutes / 60;
  return Number.isInteger(hours) ? `${hours} hr` : `${hours.toFixed(1)} hr`;
}

/** A sortable date for an event: the next start, or the 1st of its usual month. */
export function sortDate(event: EventCard, today: Date): number {
  if (event.next) return parseDate(event.next.start_date).getTime();
  if (event.expected_month) {
    const year =
      event.expected_month - 1 >= today.getMonth() ? today.getFullYear() : today.getFullYear() + 1;
    return new Date(year, event.expected_month - 1, 1).getTime();
  }
  return Number.MAX_SAFE_INTEGER;
}

export function monthKey(event: EventCard, today: Date): string {
  const time = sortDate(event, today);
  if (time === Number.MAX_SAFE_INTEGER) return "Date unknown";
  const d = new Date(time);
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

/** "Happening now", "Tomorrow", "In 3 weeks", "In 5 months"... ("~" when estimated). */
export function howSoon(startIso: string, endIso: string | null, estimated: boolean, today = startOfToday()): string {
  const start = parseDate(startIso);
  const end = parseDate(endIso ?? startIso);
  if (start <= today && end >= today) return "Happening now";
  if (end < today) return "Past";

  const days = Math.round((start.getTime() - today.getTime()) / DAY_MS);
  const about = estimated ? "~" : "";
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days < 14) return `In ${about}${days} days`;
  if (days < 60) return `In ${about}${Math.round(days / 7)} weeks`;
  if (days < 548) return `In ${about}${Math.round(days / 30.44)} months`;
  return `In ${about}${Math.round(days / 365.25)} years`;
}

/** howSoon for a card: its next date, or the month it usually happens in. */
export function howSoonForEvent(event: EventCard, today = startOfToday()): string | null {
  if (event.next) {
    return howSoon(event.next.start_date, event.next.end_date, event.next.date_status === "estimated", today);
  }
  if (event.expected_month) {
    const months = (event.expected_month - 1 - today.getMonth() + 12) % 12;
    return months === 0 ? "This month?" : `In ~${months} ${months === 1 ? "month" : "months"}`;
  }
  return null;
}

export function toIso(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function relativeDay(iso: string): string {
  const then = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return then.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
