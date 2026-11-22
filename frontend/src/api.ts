import type {
  CalendarEntry,
  DiscoveryRun,
  EventCard,
  EventDetail,
  EventUpdate,
  Meta,
  Settings,
  SettingsUpdate,
} from "./types";

// Empty in production, where the API serves the built frontend from the same
// origin. Vite's dev server runs on a different port, so it needs the host.
const BASE = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error("Can't reach the ConQuest server. Is `python run_api.py` running?");
  }

  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return (await response.json()) as T;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;

    if (typeof detail === "string") return detail;
    // FastAPI validation errors arrive as a list of field problems.
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item?.msg ?? "Invalid input").join("; ");
    }
  } catch {
    // Fall through to the status text.
  }
  return `Request failed (${response.status})`;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  events: () => request<EventCard[]>("/api/events"),
  event: (id: number) => request<EventDetail>(`/api/events/${id}`),
  updateEvent: (id: number, update: EventUpdate) =>
    request<EventDetail>(`/api/events/${id}`, { method: "PATCH", body: JSON.stringify(update) }),
  markSeen: () => request<Settings>("/api/events/mark-seen", { method: "POST" }),
  settings: () => request<Settings>("/api/settings"),
  saveSettings: (update: SettingsUpdate) =>
    request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(update) }),
  runs: () => request<DiscoveryRun[]>("/api/runs"),
  calendar: () => request<CalendarEntry[]>("/api/calendar"),
};

// Plain links (downloads), not fetches: the browser saves the .ics file.
export const icsUrl = {
  event: (id: number) => `${BASE}/api/events/${id}/calendar.ics`,
  mine: () => `${BASE}/api/calendar/mine.ics`,
};
