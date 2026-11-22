import { icsUrl } from "../api";
import { sortDate } from "../format";
import type { EventCard as Event, Meta, Rating, Status } from "../types";
import { EventCard } from "./EventCard";

interface Props {
  events: Event[];
  meta: Meta;
  onOpen: (id: number) => void;
  onRate: (id: number, rating: Rating) => void;
  onStatus: (id: number, status: Status) => void;
}

const SECTIONS: { status: Status; title: string; empty: string }[] = [
  { status: "going", title: "🎟️ Going", empty: "Mark an event as Going once you have tickets." },
  {
    status: "interested",
    title: "📅 On my calendar",
    empty: "Click 📅 + on any event to put it on your calendar.",
  },
  { status: "went", title: "✅ Been there", empty: "Events you've been to will show up here." },
];

export function MyListView({ events, meta, onOpen, onRate, onStatus }: Props) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const hasChosen = events.some((e) => e.status === "going" || e.status === "interested");

  return (
    <div className="view">
      {hasChosen && (
        <div className="export-bar">
          <span>Put these on your phone or Google Calendar:</span>
          <a className="button" href={icsUrl.mine()}>
            ⬇ Export my calendar (.ics)
          </a>
        </div>
      )}
      {SECTIONS.map((section) => {
        const items = events
          .filter((e) => e.status === section.status)
          .sort((a, b) => sortDate(a, today) - sortDate(b, today));
        return (
          <section key={section.status} className="list-section">
            <h2>
              {section.title} <span className="count">{items.length}</span>
            </h2>
            {items.length === 0 ? (
              <p className="muted">{section.empty}</p>
            ) : (
              <div className="grid">
                {items.map((event) => (
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
            )}
          </section>
        );
      })}
    </div>
  );
}
