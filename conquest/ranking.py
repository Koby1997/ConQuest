"""Turning stored events into a ranked list.

Nothing in here uses AI. The match score starts from the interest score the
research session gave each event, then:

- a thumbs up/down on an event moves that event a lot (+/-25),
- every thumb also teaches its categories a little (+/-6 per thumb, capped),
  so liking two maker events nudges every other maker event up,
- the manual per-category boosts from Settings add up to +/-20.

Distance never changes the score. It decides whether an event is within the
drive limit for its size, and events outside it are hidden unless asked for.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from conquest.categories import DEFAULT_DRIVE_LIMITS
from conquest.geo import estimate_drive_minutes
from conquest.models import EventOccurrence, EventSeries, Settings

NEUTRAL_SCORE = 50
OWN_RATING_POINTS = 25
POINTS_PER_THUMB = 6
MAX_LEARNED_POINTS = 30
POINTS_PER_BOOST = 10


@dataclass
class RankedEvent:
    series: EventSeries
    next_occurrence: EventOccurrence | None
    expected_month: int | None
    drive_minutes: int | None
    drive_limit: int
    within_range: bool | None
    match_score: int
    is_new: bool


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def learned_category_points(all_series: list[EventSeries]) -> dict[str, float]:
    """Points per category learned from every thumbs up/down given so far."""
    totals: dict[str, float] = defaultdict(float)
    for series in all_series:
        if not series.rating:
            continue
        categories = series.categories or ["other"]
        # An event in three categories teaches each of them a third as much.
        share = series.rating / len(categories)
        for category in categories:
            totals[category] += share
    return {
        category: _clamp(total * POINTS_PER_THUMB, -MAX_LEARNED_POINTS, MAX_LEARNED_POINTS)
        for category, total in totals.items()
    }


def match_score(series: EventSeries, learned: dict[str, float], boosts: dict[str, int]) -> int:
    base = series.ai_interest_score if series.ai_interest_score is not None else NEUTRAL_SCORE
    categories = series.categories or ["other"]
    learned_points = sum(learned.get(c, 0.0) for c in categories) / len(categories)
    boost_points = sum(boosts.get(c, 0) for c in categories) / len(categories) * POINTS_PER_BOOST
    rating_points = series.rating * OWN_RATING_POINTS
    return round(_clamp(base + learned_points + boost_points + rating_points, 0, 100))


def next_occurrence(series: EventSeries, today: date) -> EventOccurrence | None:
    upcoming = [o for o in series.occurrences if o.last_day >= today]
    return min(upcoming, key=lambda o: o.start_date, default=None)


def expected_month(series: EventSeries, today: date) -> int | None:
    """The next month the event usually happens in, when no dates are known."""
    if not series.usual_months or not series.active:
        return None
    months = sorted(series.usual_months)
    later = [m for m in months if m >= today.month]
    return later[0] if later else months[0]


def _located(series: EventSeries, preferred: EventOccurrence | None) -> EventOccurrence | None:
    if preferred is not None and preferred.lat is not None:
        return preferred
    located = [o for o in series.occurrences if o.lat is not None]
    return max(located, key=lambda o: o.start_date, default=None)


def rank_series(series: EventSeries, settings: Settings, learned: dict[str, float], today: date) -> RankedEvent:
    upcoming = next_occurrence(series, today)
    place = _located(series, upcoming)

    drive = None
    if place is not None and place.lat is not None and place.lng is not None:
        drive = estimate_drive_minutes(settings.home_lat, settings.home_lng, place.lat, place.lng)

    limits = {**DEFAULT_DRIVE_LIMITS, **(settings.drive_limits or {})}
    limit = int(limits.get(series.size_tier, limits["regional"]))
    last_seen: datetime | None = settings.last_seen_new_at

    return RankedEvent(
        series=series,
        next_occurrence=upcoming,
        expected_month=None if upcoming else expected_month(series, today),
        drive_minutes=drive,
        drive_limit=limit,
        within_range=None if drive is None else drive <= limit,
        match_score=match_score(series, learned, settings.category_boosts or {}),
        is_new=last_seen is None or series.first_seen > last_seen,
    )


def rank_all(all_series: list[EventSeries], settings: Settings, today: date) -> list[RankedEvent]:
    learned = learned_category_points(all_series)
    ranked = [rank_series(series, settings, learned, today) for series in all_series]
    ranked.sort(key=lambda r: (-r.match_score, r.series.name.lower()))
    return ranked
