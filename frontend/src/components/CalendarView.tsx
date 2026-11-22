import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { api, icsUrl } from "../api";
import { colorFor } from "../categories";
import { formatDates, formatDrive, formatPrice, howSoon, startOfToday, toIso } from "../format";
import type { CalendarEntry, Meta } from "../types";

interface Props {
  meta: Meta;
  /** Bumped by the parent whenever events change, so the calendar reloads. */
  refreshKey: number;
  onOpen: (seriesId: number) => void;
}

type Scope = "all" | "mine";
const SCOPE_KEY = "conquest.calendarScope";
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MAX_CHIPS_PER_DAY = 3;

// My calendar: what you've chosen, plus what you went to.
const MINE = new Set(["interested", "going", "went"]);

const lastDay = (e: CalendarEntry) => e.end_date ?? e.start_date;

export function CalendarView({ meta, refreshKey, onOpen }: Props) {
  const today = useMemo(startOfToday, []);
  const todayIso = toIso(today);
  const [entries, setEntries] = useState<CalendarEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScopeState] = useState<Scope>(() =>
    localStorage.getItem(SCOPE_KEY) === "mine" ? "mine" : "all",
  );
  const [includeFar, setIncludeFar] = useState(false);
  const [month, setMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1));

  const setScope = (next: Scope) => {
    setScopeState(next);
    localStorage.setItem(SCOPE_KEY, next);
  };

  useEffect(() => {
    api
      .calendar()
      .then((list) => {
        setEntries(list);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, [refreshKey]);

  const visible = useMemo(() => {
    if (!entries) return [];
    return entries.filter((e) =>
      scope === "mine"
        ? MINE.has(e.status)
        : e.status !== "skip" && (includeFar || e.within_range !== false),
    );
  }, [entries, scope, includeFar]);

  const hiddenFar = (entries ?? []).filter(
    (e) => scope === "all" && e.status !== "skip" && e.within_range === false,
  ).length;

  // The grid runs from the Sunday before the 1st to the Saturday after the last day.
  const monthStart = toIso(month);
  const monthEnd = toIso(new Date(month.getFullYear(), month.getMonth() + 1, 0));
  const gridStart = new Date(month);
  gridStart.setDate(1 - month.getDay());
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const weeks = Math.ceil((month.getDay() + daysInMonth) / 7);
  const cells = Array.from({ length: weeks * 7 }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return d;
  });

  // ISO dates compare correctly as strings.
  const onDay = (iso: string) => visible.filter((e) => e.start_date <= iso && lastDay(e) >= iso);
  const thisMonth = visible.filter((e) => e.start_date <= monthEnd && lastDay(e) >= monthStart);
  const nextLater = visible.find((e) => e.start_date > monthEnd && lastDay(e) >= todayIso);
  const nextUpcoming = visible.find((e) => lastDay(e) >= todayIso);

  const shiftMonth = (delta: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
  const jumpTo = (iso: string) => {
    const [y, m] = iso.split("-").map(Number);
    setMonth(new Date(y, m - 1, 1));
  };
  const monthLabel = month.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const isCurrentMonth = month.getFullYear() === today.getFullYear() && month.getMonth() === today.getMonth();

  return (
    <div className="view calendar">
      <div className="cal-toolbar">
        <div className="segmented" role="group" aria-label="Which events">
          <button className={scope === "all" ? "segmented--on" : ""} onClick={() => setScope("all")}>
            🗓️ All events
          </button>
          <button className={scope === "mine" ? "segmented--on" : ""} onClick={() => setScope("mine")}>
            📅 My calendar
          </button>
        </div>

        <div className="cal-nav">
          <button className="icon-button" onClick={() => shiftMonth(-1)} aria-label="Previous month">
            ◀
          </button>
          <h2>{monthLabel}</h2>
          <button className="icon-button" onClick={() => shiftMonth(1)} aria-label="Next month">
            ▶
          </button>
          {!isCurrentMonth && (
            <button className="link-button" onClick={() => setMonth(new Date(today.getFullYear(), today.getMonth(), 1))}>
              Today
            </button>
          )}
        </div>

        <div className="cal-extra">
          {scope === "all" ? (
            <label className="checkbox">
              <input type="checkbox" checked={includeFar} onChange={(e) => setIncludeFar(e.target.checked)} />
              Include farther events{hiddenFar > 0 && !includeFar ? ` (${hiddenFar})` : ""}
            </label>
          ) : (
            <a className="button" href={icsUrl.mine()} title="Open in Google Calendar, Outlook or your phone">
              ⬇ Export (.ics)
            </a>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {!entries && !error && <p className="muted">Loading…</p>}

      {entries && scope === "mine" && visible.length === 0 && (
        <div className="hint">
          Nothing on your calendar yet. Click <strong>📅 +</strong> on any event (or "Add to my calendar" in its
          details) and it will show up here.
        </div>
      )}

      <div className="cal-grid" role="grid" aria-label={monthLabel}>
        {WEEKDAYS.map((d) => (
          <div key={d} className="cal-weekday" role="columnheader">
            {d}
          </div>
        ))}
        {cells.map((day) => {
          const iso = toIso(day);
          const items = onDay(iso);
          const outside = day.getMonth() !== month.getMonth();
          return (
            <div
              key={iso}
              role="gridcell"
              className={`cal-day ${outside ? "cal-day--outside" : ""} ${iso === todayIso ? "cal-day--today" : ""}`}
            >
              <span className="cal-day__num">{day.getDate()}</span>
              {items.slice(0, MAX_CHIPS_PER_DAY).map((e) => (
                <CalendarChip key={e.occurrence_id} entry={e} iso={iso} todayIso={todayIso} scope={scope} onOpen={onOpen} />
              ))}
              {items.length > MAX_CHIPS_PER_DAY && (
                <span className="cal-more">+{items.length - MAX_CHIPS_PER_DAY} more</span>
              )}
            </div>
          );
        })}
      </div>
      <p className="muted small cal-legend">
        Dashed = estimated dates (not announced yet) · ✓ = on my calendar · faded = already happened
      </p>

      <section className="agenda">
        <h2>
          {scope === "mine" ? "My events" : "Events"} in {monthLabel}
        </h2>
        {thisMonth.length === 0 ? (
          <p className="muted">
            Nothing in {monthLabel}.{" "}
            {(nextLater ?? nextUpcoming) && (
              <>
                Next up: <strong>{(nextLater ?? nextUpcoming)!.name}</strong> (
                {formatDates((nextLater ?? nextUpcoming)!)}).{" "}
                <button className="link-button" onClick={() => jumpTo((nextLater ?? nextUpcoming)!.start_date)}>
                  Go there →
                </button>
              </>
            )}
          </p>
        ) : (
          <ul className="agenda-list">
            {thisMonth.map((e) => {
              const estimated = e.date_status === "estimated";
              return (
                <li key={e.occurrence_id}>
                  <button
                    className={`agenda-item ${lastDay(e) < todayIso ? "agenda-item--past" : ""}`}
                    style={{ "--chip": colorFor(e.categories[0]) } as CSSProperties}
                    onClick={() => onOpen(e.series_id)}
                  >
                    <span className="agenda-item__date">
                      {formatDates(e)}
                      <span className="soon">{howSoon(e.start_date, e.end_date, estimated, today)}</span>
                    </span>
                    <span className="agenda-item__name">
                      {e.name}
                      {(e.status === "interested" || e.status === "going") && <span className="chosen-mark"> ✓</span>}
                      {e.status === "going" && <span className="badge badge--status-going">Going</span>}
                      {e.status === "went" && <span className="badge badge--status-went">Went</span>}
                    </span>
                    <span className="agenda-item__meta">
                      {e.city}, {e.state} · {formatDrive(e.drive_minutes)} · {formatPrice(e)} ·{" "}
                      {meta.categories[e.categories[0]] ?? ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {thisMonth.length > 0 && nextLater && (
          <p className="muted small">
            After this month: <strong>{nextLater.name}</strong> ({formatDates(nextLater)}).{" "}
            <button className="link-button" onClick={() => jumpTo(nextLater.start_date)}>
              Go there →
            </button>
          </p>
        )}
      </section>
    </div>
  );
}

interface ChipProps {
  entry: CalendarEntry;
  iso: string;
  todayIso: string;
  scope: Scope;
  onOpen: (seriesId: number) => void;
}

function CalendarChip({ entry, iso, todayIso, scope, onOpen }: ChipProps) {
  const estimated = entry.date_status === "estimated";
  const past = lastDay(entry) < todayIso;
  const continues = entry.start_date < iso;
  const chosen = entry.status === "interested" || entry.status === "going";
  const classes = [
    "cal-chip",
    estimated && "cal-chip--est",
    past && "cal-chip--past",
    continues && "cal-chip--cont",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      className={classes}
      style={{ "--chip": colorFor(entry.categories[0]) } as CSSProperties}
      onClick={() => onOpen(entry.series_id)}
      title={`${entry.name} · ${formatDates(entry)} · ${entry.city}`}
    >
      {scope === "all" && chosen && "✓ "}
      {entry.name}
    </button>
  );
}
