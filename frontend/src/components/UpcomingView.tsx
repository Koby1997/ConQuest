import { useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { CATEGORY_ICONS, colorFor } from "../categories";
import { monthKey, sortDate } from "../format";
import type { EventCard as Event, Meta, Rating, Status } from "../types";
import { EventCard } from "./EventCard";

interface Props {
  events: Event[];
  meta: Meta;
  onOpen: (id: number) => void;
  onRate: (id: number, rating: Rating) => void;
  onStatus: (id: number, status: Status) => void;
  onMarkSeen: () => void;
}

type Sort = "match" | "date";
const SORT_KEY = "conquest.sort";

export function UpcomingView({ events, meta, onOpen, onRate, onStatus, onMarkSeen }: Props) {
  const [query, setQuery] = useState("");
  const [categories, setCategories] = useState<Set<string>>(new Set());
  const [sort, setSortState] = useState<Sort>(() =>
    localStorage.getItem(SORT_KEY) === "date" ? "date" : "match",
  );
  const setSort = (next: Sort) => {
    setSortState(next);
    localStorage.setItem(SORT_KEY, next);
  };
  const [includeFar, setIncludeFar] = useState(false);
  const [showSkipped, setShowSkipped] = useState(false);
  const [onlyNew, setOnlyNew] = useState(false);
  const [maxPrice, setMaxPrice] = useState("");

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const upcoming = useMemo(
    // Anything with a future date, or a usual month to expect it in.
    () => events.filter((e) => e.active && (e.next !== null || e.expected_month !== null)),
    [events],
  );

  const hiddenFar = upcoming.filter((e) => e.within_range === false).length;
  const newCount = upcoming.filter((e) => e.is_new).length;

  const visible = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const limit = maxPrice === "" ? null : Number(maxPrice);

    const kept = upcoming.filter((e) => {
      if (!showSkipped && e.status === "skip") return false;
      if (!includeFar && e.within_range === false) return false;
      if (onlyNew && !e.is_new) return false;
      if (categories.size > 0 && !e.categories.some((c) => categories.has(c))) return false;
      if (limit !== null && e.next?.price_min != null && e.next.price_min > limit) return false;
      if (words.length > 0) {
        const haystack = [e.name, ...e.aliases, e.description, e.next?.city ?? "", e.next?.venue_name ?? ""]
          .join(" ")
          .toLowerCase();
        if (!words.every((w) => haystack.includes(w))) return false;
      }
      return true;
    });

    return kept.sort((a, b) =>
      sort === "match"
        ? b.match_score - a.match_score || sortDate(a, today) - sortDate(b, today)
        : sortDate(a, today) - sortDate(b, today) || b.match_score - a.match_score,
    );
  }, [upcoming, query, categories, sort, includeFar, showSkipped, onlyNew, maxPrice, today]);

  const toggleCategory = (slug: string) => {
    const next = new Set(categories);
    if (next.has(slug)) next.delete(slug);
    else next.add(slug);
    setCategories(next);
  };

  if (events.length === 0) {
    return <EmptyState />;
  }

  // In date order, group cards under month headings.
  const groups: { label: string; items: Event[] }[] = [];
  if (sort === "date") {
    for (const event of visible) {
      const label = monthKey(event, today);
      const last = groups[groups.length - 1];
      if (last && last.label === label) last.items.push(event);
      else groups.push({ label, items: [event] });
    }
  } else {
    groups.push({ label: "", items: visible });
  }

  return (
    <div className="view">
      {newCount > 0 && (
        <div className="banner">
          <span>
            🎉 <strong>{newCount}</strong> new {newCount === 1 ? "event" : "events"} since you last looked.
          </span>
          <span className="banner__actions">
            <button className="link-button" onClick={() => setOnlyNew(!onlyNew)}>
              {onlyNew ? "Show all" : "Show only new"}
            </button>
            <button className="link-button" onClick={onMarkSeen}>
              Mark all as seen
            </button>
          </span>
        </div>
      )}

      <div className="filters">
        <input
          className="search"
          type="search"
          placeholder="Search events, venues, cities…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="filters__row">
          <div className="segmented" role="group" aria-label="Order events by">
            <button className={sort === "match" ? "segmented--on" : ""} onClick={() => setSort("match")}>
              ⭐ Best match
            </button>
            <button className={sort === "date" ? "segmented--on" : ""} onClick={() => setSort("date")}>
              📅 Soonest first
            </button>
          </div>
          <label>
            Max ticket ${" "}
            <input
              className="price-input"
              type="number"
              min={0}
              step={5}
              placeholder="any"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={includeFar} onChange={(e) => setIncludeFar(e.target.checked)} />
            Include farther events{hiddenFar > 0 && !includeFar ? ` (${hiddenFar})` : ""}
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={showSkipped} onChange={(e) => setShowSkipped(e.target.checked)} />
            Show "not for me"
          </label>
        </div>
        <div className="chips chips--filter">
          {Object.entries(meta.categories).map(([slug, label]) => (
            <button
              key={slug}
              className={`chip chip--toggle ${categories.has(slug) ? "chip--on" : ""}`}
              style={{ "--chip": colorFor(slug) } as CSSProperties}
              onClick={() => toggleCategory(slug)}
              aria-pressed={categories.has(slug)}
            >
              {CATEGORY_ICONS[slug]} {label}
            </button>
          ))}
          {categories.size > 0 && (
            <button className="link-button" onClick={() => setCategories(new Set())}>
              Clear
            </button>
          )}
        </div>
      </div>

      <p className="muted small">
        Showing {visible.length} of {upcoming.length} upcoming events
      </p>

      {visible.length === 0 && <p className="empty">Nothing matches these filters.</p>}

      {groups.map((group) => (
        <section key={group.label || "all"}>
          {group.label && <h2 className="month-heading">{group.label}</h2>}
          <div className="grid">
            {group.items.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                meta={meta}
                onOpen={onOpen}
                onRate={onRate}
                onStatus={onStatus}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="empty-state">
      <h2>No events yet</h2>
      <p>ConQuest fills up when you run a search from Claude Code:</p>
      <ol>
        <li>Open this project folder in VS Code and open the Claude Code panel.</li>
        <li>
          Type <code>/discover seed</code> for the first big search (later, just <code>/discover</code> once a
          week).
        </li>
        <li>Come back here and refresh.</li>
      </ol>
    </div>
  );
}
