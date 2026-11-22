import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { CalendarView } from "./components/CalendarView";
import { EventDetail } from "./components/EventDetail";
import { MyListView } from "./components/MyListView";
import { SettingsView } from "./components/SettingsView";
import { UpcomingView } from "./components/UpcomingView";
import type { EventCard, Meta, Rating, Status } from "./types";

type Tab = "upcoming" | "calendar" | "mylist" | "settings";
const TABS: { id: Tab; label: string }[] = [
  { id: "upcoming", label: "Upcoming" },
  { id: "calendar", label: "Calendar" },
  { id: "mylist", label: "My List" },
  { id: "settings", label: "Settings" },
];

const tabFromHash = (): Tab => {
  const hash = window.location.hash.slice(1);
  return TABS.find((t) => t.id === hash)?.id ?? "upcoming";
};

export default function App() {
  // The tab lives in the URL hash (#calendar) so it survives a reload.
  const [tab, setTabState] = useState<Tab>(tabFromHash);
  const setTab = (next: Tab) => {
    setTabState(next);
    const url = window.location.pathname + window.location.search + (next === "upcoming" ? "" : `#${next}`);
    window.history.replaceState(null, "", url);
  };

  const [meta, setMeta] = useState<Meta | null>(null);
  const [events, setEvents] = useState<EventCard[]>([]);
  // Bumped after every change so views that fetch their own data (the calendar) reload too.
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // ?event=12 opens that event, so an event can be bookmarked or linked.
  const [openId, setOpenIdState] = useState<number | null>(() => {
    const id = Number(new URLSearchParams(window.location.search).get("event"));
    return Number.isInteger(id) && id > 0 ? id : null;
  });
  const setOpenId = useCallback((id: number | null) => {
    setOpenIdState(id);
    const url = new URL(window.location.href);
    if (id === null) url.searchParams.delete("event");
    else url.searchParams.set("event", String(id));
    window.history.replaceState(null, "", url);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [m, e] = await Promise.all([api.meta(), api.events()]);
      setMeta(m);
      setEvents(e);
      setVersion((v) => v + 1);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Update the card immediately, then refresh to pick up new scores.
  const change = async (id: number, update: { rating?: Rating; status?: Status }) => {
    setEvents((list) => list.map((e) => (e.id === id ? { ...e, ...update } : e)));
    try {
      await api.updateEvent(id, update);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const rate = (id: number, rating: Rating) => change(id, { rating });
  const setStatus = (id: number, status: Status) => change(id, { status });

  const markSeen = async () => {
    await api.markSeen();
    await refresh();
  };

  const myListCount = events.filter((e) => e.status === "going" || e.status === "interested").length;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__logo">🧭</span>
          <span className="brand__name">ConQuest</span>
          <span className="brand__tag">cons, expos &amp; cool stuff nearby</span>
        </div>
        <nav className="tabs" aria-label="Sections">
          {TABS.map((t) => (
            <button key={t.id} className={`tab ${tab === t.id ? "tab--on" : ""}`} onClick={() => setTab(t.id)}>
              {t.label}
              {t.id === "mylist" && myListCount > 0 && <span className="count">{myListCount}</span>}
            </button>
          ))}
        </nav>
        <button className="refresh" onClick={refresh} title="Reload events">
          ⟳
        </button>
      </header>

      <main>
        {error && <p className="error banner--error">{error}</p>}
        {loading && <p className="muted view">Loading…</p>}
        {meta && tab === "upcoming" && (
          <UpcomingView
            events={events}
            meta={meta}
            onOpen={setOpenId}
            onRate={rate}
            onStatus={setStatus}
            onMarkSeen={markSeen}
          />
        )}
        {meta && tab === "calendar" && <CalendarView meta={meta} refreshKey={version} onOpen={setOpenId} />}
        {meta && tab === "mylist" && (
          <MyListView events={events} meta={meta} onOpen={setOpenId} onRate={rate} onStatus={setStatus} />
        )}
        {meta && tab === "settings" && <SettingsView meta={meta} onSaved={refresh} />}
      </main>

      {meta && openId !== null && (
        <EventDetail eventId={openId} meta={meta} onClose={() => setOpenId(null)} onChanged={refresh} />
      )}
    </div>
  );
}
