import type { CSSProperties, MouseEvent } from "react";
import { CATEGORY_ICONS, colorFor, SIZE_LABELS } from "../categories";
import { formatDrive, formatPrice, howSoonForEvent, whenLabel } from "../format";
import { isChosen } from "../types";
import type { EventCard as Event, Meta, Rating, Status } from "../types";

interface Props {
  event: Event;
  meta: Meta;
  onOpen: (id: number) => void;
  onRate: (id: number, rating: Rating) => void;
  onStatus: (id: number, status: Status) => void;
}

export function EventCard({ event, meta, onOpen, onRate, onStatus }: Props) {
  const color = colorFor(event.categories[0]);
  const estimated = event.next?.date_status === "estimated" || (!event.next && event.expected_month);
  const place = event.next ? `${event.next.city}, ${event.next.state}` : null;
  const chosen = isChosen(event.status);
  const soon = howSoonForEvent(event);

  const rate = (value: Rating) => (e: MouseEvent) => {
    e.stopPropagation();
    onRate(event.id, event.rating === value ? 0 : value);
  };

  const toggleCalendar = (e: MouseEvent) => {
    e.stopPropagation();
    onStatus(event.id, chosen ? "none" : "interested");
  };

  return (
    <article
      className={`card ${event.status === "skip" ? "card--muted" : ""} ${chosen ? "card--chosen" : ""}`}
      style={{ "--accent": color } as CSSProperties}
      onClick={() => onOpen(event.id)}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && e.target === e.currentTarget && onOpen(event.id)}
      tabIndex={0}
      aria-label={`Open ${event.name}`}
    >
      <div className="card__top">
        <div className="card__badges">
          {event.is_new && <span className="badge badge--new">New</span>}
          {estimated && <span className="badge badge--est">Est. dates</span>}
          {event.within_range === false && <span className="badge badge--far">Farther</span>}
          {(event.status === "going" || event.status === "went") && (
            <span className={`badge badge--status-${event.status}`}>{meta.statuses[event.status]}</span>
          )}
        </div>
        <span className="match" title={event.interest_reason ?? "How well this matches your interests"}>
          {event.match_score}
          <small>% match</small>
        </span>
      </div>

      <h3 className="card__title">{event.name}</h3>

      <p className="card__when">
        {whenLabel(event)}
        {soon && <span className="soon">{soon}</span>}
      </p>
      <p className="card__meta">
        {place && <span>{place}</span>}
        <span>{formatDrive(event.drive_minutes)}</span>
        <span>{formatPrice(event.next)}</span>
      </p>

      <p className="card__desc">{event.description}</p>

      <div className="chips">
        {event.categories.map((c) => (
          <span key={c} className="chip" style={{ "--chip": colorFor(c) } as CSSProperties}>
            {CATEGORY_ICONS[c]} {meta.categories[c] ?? c}
          </span>
        ))}
        <span className="chip chip--plain">{SIZE_LABELS[event.size_tier] ?? event.size_tier}</span>
      </div>

      <div className="card__bottom">
        <button
          className={`cal-toggle ${chosen ? "cal-toggle--on" : ""}`}
          onClick={toggleCalendar}
          title={chosen ? "Click to take it off your calendar" : "Put this on My calendar"}
          aria-pressed={chosen}
        >
          {event.status === "going" ? "🎟️ Going ✓" : chosen ? "📅 On my calendar ✓" : "📅 Add to my calendar"}
        </button>
        <div className="thumbs">
          <button
            className={`thumb ${event.rating === 1 ? "thumb--on" : ""}`}
            onClick={rate(1)}
            title="More like this"
            aria-pressed={event.rating === 1}
          >
            👍
          </button>
          <button
            className={`thumb ${event.rating === -1 ? "thumb--on thumb--down" : ""}`}
            onClick={rate(-1)}
            title="Less like this"
            aria-pressed={event.rating === -1}
          >
            👎
          </button>
        </div>
      </div>
    </article>
  );
}
