import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { api, icsUrl } from "../api";
import { CATEGORY_ICONS, colorFor, SIZE_LABELS } from "../categories";
import {
  formatDates,
  formatDrive,
  formatHours,
  formatPrice,
  hostname,
  howSoon,
  monthName,
  parseDate,
  relativeDay,
} from "../format";
import type { EventDetail as Detail, EventUpdate, Meta, Occurrence, Status } from "../types";

interface Props {
  eventId: number;
  meta: Meta;
  onClose: () => void;
  onChanged: () => void;
}

// "On my calendar" and "Going" both put the event on My calendar.
const STATUS_BUTTONS: { value: Status; label: string; on?: string }[] = [
  { value: "interested", label: "📅 Add to my calendar", on: "📅 On my calendar ✓" },
  { value: "going", label: "🎟️ Going (got tickets)" },
  { value: "went", label: "✅ Went" },
  { value: "skip", label: "🙈 Not for me" },
];

export function EventDetail({ eventId, meta, onClose, onChanged }: Props) {
  const [event, setEvent] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [notesSaved, setNotesSaved] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setEvent(null);
    api
      .event(eventId)
      .then((detail) => {
        if (cancelled) return;
        setEvent(detail);
        setNotes(detail.notes);
        setNotesSaved(true);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const update = async (change: EventUpdate) => {
    try {
      const detail = await api.updateEvent(eventId, change);
      setEvent(detail);
      if (change.notes !== undefined) setNotesSaved(true);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const isPast = (o: Occurrence) => parseDate(o.end_date ?? o.start_date) < today;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={event?.name ?? "Event details"}
        style={{ "--accent": colorFor(event?.categories[0]) } as CSSProperties}
      >
        <button className="drawer__close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {error && <p className="error">{error}</p>}
        {!event && !error && <p className="muted">Loading…</p>}

        {event && (
          <>
            <header className="drawer__header">
              <div className="chips">
                {event.categories.map((c) => (
                  <span key={c} className="chip" style={{ "--chip": colorFor(c) } as CSSProperties}>
                    {CATEGORY_ICONS[c]} {meta.categories[c] ?? c}
                  </span>
                ))}
                <span className="chip chip--plain">{SIZE_LABELS[event.size_tier]}</span>
                <span className="chip chip--plain">{meta.recurrences[event.recurrence] ?? event.recurrence}</span>
              </div>
              <h2>{event.name}</h2>
              {event.aliases.length > 0 && <p className="muted">Also known as {event.aliases.join(", ")}</p>}
              {!event.active && <p className="warning">This event appears to have ended.</p>}
            </header>

            <section className="match-box">
              <span className="match match--big">
                {event.match_score}
                <small>% match</small>
              </span>
              <p>{event.interest_reason ?? "No interest notes yet."}</p>
            </section>

            <section className="actions">
              <div className="status-buttons">
                {STATUS_BUTTONS.map((b) => (
                  <button
                    key={b.value}
                    className={`pill ${event.status === b.value ? "pill--on" : ""}`}
                    onClick={() => update({ status: event.status === b.value ? "none" : b.value })}
                  >
                    {event.status === b.value && b.on ? b.on : b.label}
                  </button>
                ))}
              </div>
              <div className="thumbs">
                <button
                  className={`thumb ${event.rating === 1 ? "thumb--on" : ""}`}
                  onClick={() => update({ rating: event.rating === 1 ? 0 : 1 })}
                  title="More like this"
                >
                  👍
                </button>
                <button
                  className={`thumb ${event.rating === -1 ? "thumb--on thumb--down" : ""}`}
                  onClick={() => update({ rating: event.rating === -1 ? 0 : -1 })}
                  title="Less like this"
                >
                  👎
                </button>
              </div>
            </section>

            <section>
              <p className="description">{event.description}</p>
              {event.website && (
                <a className="link" href={event.website} target="_blank" rel="noreferrer">
                  {hostname(event.website)} ↗
                </a>
              )}
            </section>

            <section>
              <h3>Next up</h3>
              {event.next ? (
                <OccurrenceBlock occurrence={event.next} eventId={event.id} />
              ) : event.expected_month ? (
                <p>
                  No dates announced yet. It usually happens in <strong>{monthName(event.expected_month)}</strong>.
                </p>
              ) : (
                <p className="muted">No upcoming dates known.</p>
              )}
              {event.within_range === false && (
                <p className="warning">
                  Farther than your {formatHours(event.drive_limit)} limit for {SIZE_LABELS[event.size_tier]?.toLowerCase()}{" "}
                  events.
                </p>
              )}
            </section>

            <section>
              <h3>What people say</h3>
              {event.review_summary ? (
                <>
                  <p>{event.review_summary}</p>
                  {(event.review_pros.length > 0 || event.review_cons.length > 0) && (
                    <div className="pros-cons">
                      {event.review_pros.length > 0 && (
                        <ul className="pros">
                          {event.review_pros.map((p) => (
                            <li key={p}>{p}</li>
                          ))}
                        </ul>
                      )}
                      {event.review_cons.length > 0 && (
                        <ul className="cons">
                          {event.review_cons.map((c) => (
                            <li key={c}>{c}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  {event.review_sources.length > 0 && (
                    <p className="sources">
                      Sources:{" "}
                      {event.review_sources.map((url, i) => (
                        <span key={url}>
                          {i > 0 && " · "}
                          <a href={url} target="_blank" rel="noreferrer">
                            {hostname(url)}
                          </a>
                        </span>
                      ))}
                    </p>
                  )}
                </>
              ) : (
                <p className="muted">No reviews found yet.</p>
              )}
            </section>

            {event.occurrences.length > 1 && (
              <section>
                <h3>All dates</h3>
                <ul className="occurrence-list">
                  {[...event.occurrences].reverse().map((o) => (
                    <li key={o.id} className={isPast(o) ? "muted" : ""}>
                      {formatDates(o)} · {o.city} · {formatPrice(o)}
                      {isPast(o) && " (past)"}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section>
              <h3>My notes</h3>
              <textarea
                className="notes"
                value={notes}
                placeholder="Who to go with, what to bring, budget…"
                onChange={(e) => {
                  setNotes(e.target.value);
                  setNotesSaved(false);
                }}
                rows={3}
              />
              {!notesSaved && (
                <button className="button" onClick={() => update({ notes })}>
                  Save notes
                </button>
              )}
            </section>

            <p className="muted small">
              First found {relativeDay(event.first_seen)}
              {event.last_checked && ` · last checked ${relativeDay(event.last_checked)}`}
            </p>
          </>
        )}
      </aside>
    </div>
  );
}

function OccurrenceBlock({ occurrence, eventId }: { occurrence: Occurrence; eventId: number }) {
  const estimated = occurrence.date_status === "estimated";
  return (
    <div className="occurrence">
      <p className="occurrence__when">
        {formatDates(occurrence)}
        <span className="soon">{howSoon(occurrence.start_date, occurrence.end_date, estimated)}</span>
        {estimated && <span className="badge badge--est">Estimated from past years</span>}
      </p>
      <p>
        {occurrence.venue_name && <strong>{occurrence.venue_name}</strong>}
        {occurrence.venue_name && <br />}
        {occurrence.address ?? `${occurrence.city}, ${occurrence.state}`}
      </p>
      <p>{formatDrive(occurrence.drive_minutes)} from home</p>
      <p>
        <strong>{formatPrice(occurrence)}</strong>
        {occurrence.price_notes && <span className="muted"> · {occurrence.price_notes}</span>}
      </p>
      <div className="links">
        {occurrence.ticket_url && (
          <a className="button button--primary" href={occurrence.ticket_url} target="_blank" rel="noreferrer">
            Tickets ↗
          </a>
        )}
        <a
          className="button"
          href={icsUrl.event(eventId)}
          title="Download a calendar file you can open in Google Calendar, Outlook or your phone"
        >
          ⬇ Add to Google/Outlook (.ics)
        </a>
        {occurrence.source_urls.slice(0, 3).map((url) => (
          <a key={url} className="link" href={url} target="_blank" rel="noreferrer">
            {hostname(url)} ↗
          </a>
        ))}
      </div>
    </div>
  );
}
