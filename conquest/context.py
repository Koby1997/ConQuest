"""What a /discover session needs to know before it starts searching.

`conquest context` prints this as JSON. It is deliberately compact: it is
read at the start of every session, so every known event costs a line, not a
paragraph.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from conquest import config
from conquest.categories import CATEGORIES, REGIONS, SIZE_TIERS
from conquest.db import get_settings
from conquest.models import DiscoveryRun, EventSeries
from conquest.ranking import next_occurrence

# Searches that count toward the rotation (refresh/rescore don't look for new events).
DISCOVERY_MODES = ("seed", "rotation", "category")
CATEGORIES_PER_ROTATION = 2
STALE_AFTER_DAYS = 45


def _iso(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()


def _months_until(month: int, today: date) -> int:
    return (month - today.month) % 12


def search_history(session: Session) -> dict[tuple[str, str], datetime]:
    """When each (category, region) pair was last searched for new events."""
    last: dict[tuple[str, str], datetime] = {}
    runs = session.scalars(select(DiscoveryRun).where(DiscoveryRun.mode.in_(DISCOVERY_MODES)))
    for run in runs:
        for category in run.categories:
            for region in run.regions:
                key = (category, region)
                if key not in last or run.created_at > last[key]:
                    last[key] = run.created_at
    return last


def suggest_categories(history: dict[tuple[str, str], datetime], count: int = CATEGORIES_PER_ROTATION) -> list[str]:
    """The categories most overdue for a search.

    Never searched anywhere comes first, then searched in only some regions
    (fewest first), then fully covered categories by their oldest search.
    """

    def overdue(category: str) -> tuple[int, datetime]:
        times = [t for region in REGIONS if (t := history.get((category, region))) is not None]
        return len(times), min(times, default=datetime.min)

    candidates = [c for c in CATEGORIES if c != "other"]
    return sorted(candidates, key=overdue)[:count]


def build_context(
    session: Session,
    *,
    today: date,
    focus_category: str | None = None,
    details: bool = False,
) -> dict:
    settings = get_settings(session)
    all_series = list(session.scalars(select(EventSeries).order_by(EventSeries.name)))

    known = []
    needs_dates = []
    for series in all_series:
        upcoming = next_occurrence(series, today)
        cities = sorted({o.city for o in series.occurrences})
        entry: dict = {"id": series.id, "name": series.name}
        if series.aliases:
            entry["aka"] = series.aliases
        if cities:
            entry["cities"] = cities
        if upcoming is not None:
            entry["next"] = f"{upcoming.start_date.isoformat()} ({upcoming.date_status})"
        elif series.usual_months:
            entry["usual_months"] = series.usual_months
        if not series.active:
            entry["inactive"] = True
        if details:
            # For /discover rescore, which scores from what's stored instead of searching.
            entry["categories"] = series.categories
            entry["size_tier"] = series.size_tier
            entry["score"] = series.ai_interest_score
            entry["rating"] = series.rating
            entry["description"] = series.description
        known.append(entry)

        if not series.active or series.recurrence == "one_time":
            continue
        confirmed_ahead = upcoming is not None and upcoming.date_status == "confirmed"
        stale = series.last_checked is None or (today - series.last_checked.date()).days > STALE_AFTER_DAYS
        if not confirmed_ahead and stale:
            soonest = min((_months_until(m, today) for m in series.usual_months), default=12)
            needs_dates.append(
                (
                    soonest,
                    {
                        "id": series.id,
                        "name": series.name,
                        "website": series.website,
                        "usual_months": series.usual_months,
                        "last_checked": _iso(series.last_checked),
                    },
                )
            )

    needs_dates.sort(key=lambda pair: pair[0])
    history = search_history(session)

    needs_review = [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description[:200],
            "next": _iso(next_occurrence(s, today).start_date) if next_occurrence(s, today) else None,
        }
        for s in all_series
        if s.needs_ai_review
    ]

    context = {
        "today": today.isoformat(),
        "home": {"label": settings.home_label, "lat": settings.home_lat, "lng": settings.home_lng},
        "drive_limits_minutes": settings.drive_limits,
        "interest_profile": settings.interest_profile,
        "category_boosts": settings.category_boosts or {},
        "categories": CATEGORIES,
        "size_tiers": SIZE_TIERS,
        "regions": REGIONS,
        "inbox_dir": str(config.INBOX_DIR),
        "known_series_count": len(all_series),
        "known_series": known,
        "needs_date_check": [entry for _, entry in needs_dates],
        "needs_ai_review": needs_review,
        # category -> region -> date last searched (null = never).
        "search_history": {
            c: {r: _iso(history.get((c, r))) for r in REGIONS} for c in CATEGORIES if c != "other"
        },
        "suggested_next": {
            "categories": [focus_category] if focus_category else suggest_categories(history),
            "regions": REGIONS,
        },
    }
    return context
