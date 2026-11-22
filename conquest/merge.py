"""Folding a validated EventBatch into the database without creating duplicates.

Research sessions will find the same events again and again (that is the
point of a weekly check), often under slightly different names. Matching an
incoming event to a known series goes from most to least certain:

1. the id the session copied from `conquest context`,
2. the same normalised name or alias ("MegaCon Orlando 2027" = "MEGACON Orlando"),
3. the same words in a different order ("Maker Faire Orlando" = "Orlando Maker Faire"),
4. a very close spelling,
5. a looser spelling *and* an edition in the same city on overlapping dates.

Within a series, an incoming edition updates the existing one closest in date
rather than adding a second copy, which is also how an estimated date
("usually May") is upgraded once the real dates are announced.

The person's own fields (rating, status, notes) are never touched here.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from conquest.geo import Geocoder, locate
from conquest.models import DiscoveryRun, EventOccurrence, EventSeries, SourceRecord, utcnow
from conquest.schemas import EventBatch, OccurrenceIn, SeriesIn

CLOSE_SPELLING = 0.88
LOOSE_SPELLING = 0.6

# How far apart two editions' start dates can be and still be "the same one".
ANNUAL_WINDOW_DAYS = 60
FREQUENT_CONFIRMED_WINDOW_DAYS = 3
FREQUENT_ESTIMATED_WINDOW_DAYS = 20

_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_FILLER_WORDS = {"the", "annual"}


@dataclass
class ImportReport:
    run_id: int | None = None
    new_series: list[str] = field(default_factory=list)
    updated_series: list[str] = field(default_factory=list)
    new_dates: list[str] = field(default_factory=list)
    newly_confirmed: list[str] = field(default_factory=list)
    updated_dates: int = 0
    score_updates: int = 0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Imported run #{self.run_id}: {len(self.new_series)} new events, "
            f"{len(self.updated_series)} updated, {len(self.new_dates)} new dates, "
            f"{len(self.newly_confirmed)} dates confirmed, {self.score_updates} re-scored."
        ]
        if self.new_series:
            lines.append("\nNew events:")
            lines += [f"  + {name}" for name in self.new_series]
        if self.newly_confirmed:
            lines.append("\nDates now confirmed:")
            lines += [f"  * {text}" for text in self.newly_confirmed]
        if self.new_dates:
            lines.append("\nNew dates:")
            lines += [f"  + {text}" for text in self.new_dates]
        if self.updated_series:
            lines.append("\nUpdated:")
            lines += [f"  ~ {name}" for name in self.updated_series]
        if self.warnings:
            lines.append("\nWarnings:")
            lines += [f"  ! {text}" for text in self.warnings]
        return "\n".join(lines)


# --- Names -----------------------------------------------------------------


def normalize_name(name: str) -> str:
    text = name.lower().replace("&", " and ").replace("'", "")
    text = _YEAR.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(word for word in text.split() if word not in _FILLER_WORDS)


def _names(series: EventSeries | SeriesIn) -> set[str]:
    keys = {normalize_name(series.name)}
    keys.update(normalize_name(alias) for alias in series.aliases)
    keys.discard("")
    return keys


def _spelling_similarity(a: set[str], b: set[str]) -> float:
    return max(
        (difflib.SequenceMatcher(None, x, y).ratio() for x in a for y in b),
        default=0.0,
    )


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date, slack_days: int = 3) -> bool:
    return (a_start - b_end).days <= slack_days and (b_start - a_end).days <= slack_days


def _shares_an_edition(existing: EventSeries, incoming: SeriesIn) -> bool:
    for old in existing.occurrences:
        for new in incoming.occurrences:
            if old.city.lower() != new.city.lower():
                continue
            if _overlaps(old.start_date, old.last_day, new.start_date, new.end_date or new.start_date):
                return True
    return False


def find_series(
    incoming: SeriesIn,
    known: list[EventSeries],
    by_id: dict[int, EventSeries],
    warnings: list[str],
) -> EventSeries | None:
    if incoming.matches_existing_series_id is not None:
        match = by_id.get(incoming.matches_existing_series_id)
        if match is not None:
            return match
        warnings.append(
            f"{incoming.name}: matches_existing_series_id {incoming.matches_existing_series_id} "
            "does not exist; matched by name instead."
        )

    incoming_names = _names(incoming)
    incoming_words = {frozenset(name.split()) for name in incoming_names}

    for series in known:
        if _names(series) & incoming_names:
            return series
    for series in known:
        if {frozenset(name.split()) for name in _names(series)} & incoming_words:
            return series

    best, best_score = None, 0.0
    for series in known:
        score = _spelling_similarity(_names(series), incoming_names)
        if score > best_score:
            best, best_score = series, score
    if best is not None and best_score >= CLOSE_SPELLING:
        return best

    for series in known:
        if _spelling_similarity(_names(series), incoming_names) >= LOOSE_SPELLING and _shares_an_edition(
            series, incoming
        ):
            return series
    return None


# --- Dates -----------------------------------------------------------------


def describe_dates(start: date, end: date | None, status: str) -> str:
    if status == "estimated":
        return f"est. {start:%B %Y}"
    if end is None or end == start:
        return f"{start:%b} {start.day}, {start.year}"
    if (start.year, start.month) == (end.year, end.month):
        return f"{start:%b} {start.day}-{end.day}, {start.year}"
    if start.year == end.year:
        return f"{start:%b} {start.day} - {end:%b} {end.day}, {start.year}"
    return f"{start:%b} {start.day}, {start.year} - {end:%b} {end.day}, {end.year}"


def find_occurrence(series: EventSeries, incoming: OccurrenceIn) -> EventOccurrence | None:
    frequent = series.recurrence == "multiple_per_year"
    best, best_gap = None, None

    for existing in series.occurrences:
        gap = abs((existing.start_date - incoming.start_date).days)
        either_estimated = "estimated" in (existing.date_status, incoming.date_status)
        if frequent:
            window = FREQUENT_ESTIMATED_WINDOW_DAYS if either_estimated else FREQUENT_CONFIRMED_WINDOW_DAYS
        else:
            window = ANNUAL_WINDOW_DAYS
        if gap <= window and (best_gap is None or gap < best_gap):
            best, best_gap = existing, gap
    return best


def _union(first: list[str], second: list[str]) -> list[str]:
    seen, merged = set(), []
    for item in [*first, *second]:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


# --- Applying ----------------------------------------------------------------


class Importer:
    def __init__(self, session: Session, geocoder: Geocoder | None, *, now: datetime | None = None) -> None:
        self.session = session
        self.geocoder = geocoder
        self.now = now or utcnow()
        self.report = ImportReport()

    def run(self, batch: EventBatch, *, file_name: str | None = None, source: str = "claude_research") -> ImportReport:
        run = DiscoveryRun(
            mode=batch.mode,
            source=source,
            categories=list(batch.categories_searched),
            regions=list(batch.regions_searched),
            file_name=file_name,
            notes=batch.notes,
            created_at=self.now,
        )
        self.session.add(run)
        self.session.flush()
        self.report.run_id = run.id

        known = list(self.session.scalars(select(EventSeries)))
        by_id = {series.id: series for series in known}

        for incoming in batch.series:
            series = find_series(incoming, known, by_id, self.report.warnings)
            if series is None:
                series = self._create_series(incoming)
                known.append(series)
                by_id[series.id] = series
                self.report.new_series.append(series.name)
            else:
                self._update_series(series, incoming)
                if series.name not in self.report.updated_series:
                    self.report.updated_series.append(series.name)

            for occurrence in incoming.occurrences:
                self._apply_occurrence(series, occurrence)

            self.session.add(
                SourceRecord(
                    series_id=series.id,
                    run_id=run.id,
                    source=source,
                    raw=incoming.model_dump(mode="json"),
                    fetched_at=self.now,
                )
            )

        for update in batch.score_updates:
            series = by_id.get(update.series_id)
            if series is None:
                self.report.warnings.append(f"score_updates: series {update.series_id} does not exist; skipped.")
                continue
            series.ai_interest_score = update.ai_interest_score
            if update.interest_reason is not None:
                series.interest_reason = update.interest_reason
            if update.categories is not None:
                series.categories = list(update.categories)
            if update.size_tier is not None:
                series.size_tier = update.size_tier
            series.needs_ai_review = False
            self.report.score_updates += 1

        self._retry_missing_locations()

        run.new_series = len(self.report.new_series)
        run.updated_series = len(self.report.updated_series)
        run.new_occurrences = len(self.report.new_dates)
        run.updated_occurrences = self.report.updated_dates
        self.session.flush()
        return self.report

    def _create_series(self, incoming: SeriesIn) -> EventSeries:
        series = EventSeries(
            name=incoming.name,
            aliases=[a for a in _union([], incoming.aliases) if normalize_name(a) != normalize_name(incoming.name)],
            website=incoming.website,
            categories=list(incoming.categories),
            size_tier=incoming.size_tier,
            recurrence=incoming.recurrence,
            usual_months=sorted(set(incoming.usual_months)),
            active=incoming.active,
            description=incoming.description,
            review_summary=incoming.review_summary,
            review_pros=list(incoming.review_pros),
            review_cons=list(incoming.review_cons),
            review_sources=list(incoming.review_sources),
            ai_interest_score=incoming.ai_interest_score,
            interest_reason=incoming.interest_reason,
            first_seen=self.now,
            last_checked=self.now,
            occurrences=[],
        )
        self.session.add(series)
        self.session.flush()
        return series

    def _update_series(self, series: EventSeries, incoming: SeriesIn) -> None:
        aliases = list(series.aliases)
        if normalize_name(incoming.name) != normalize_name(series.name):
            if incoming.rename:
                aliases.append(series.name)
                series.name = incoming.name
            else:
                aliases.append(incoming.name)
        current = normalize_name(series.name)
        merged, seen = [], {current}
        for alias in _union(aliases, incoming.aliases):
            key = normalize_name(alias)
            if key and key not in seen:
                seen.add(key)
                merged.append(alias)
        series.aliases = merged

        if incoming.website:
            series.website = incoming.website
        series.categories = list(incoming.categories)
        series.size_tier = incoming.size_tier
        if incoming.recurrence != "unknown":
            series.recurrence = incoming.recurrence
        if incoming.usual_months:
            series.usual_months = sorted(set(incoming.usual_months))
        series.active = incoming.active
        series.description = incoming.description
        if incoming.review_summary:
            series.review_summary = incoming.review_summary
            series.review_pros = list(incoming.review_pros)
            series.review_cons = list(incoming.review_cons)
            series.review_sources = _union(list(incoming.review_sources), list(series.review_sources))[:10]
        series.ai_interest_score = incoming.ai_interest_score
        if incoming.interest_reason:
            series.interest_reason = incoming.interest_reason
        series.needs_ai_review = False
        series.last_checked = self.now

    def _apply_occurrence(self, series: EventSeries, incoming: OccurrenceIn) -> None:
        existing = find_occurrence(series, incoming)
        if existing is None:
            occurrence = EventOccurrence(
                start_date=incoming.start_date,
                end_date=incoming.end_date,
                date_status=incoming.date_status,
                venue_name=incoming.venue_name,
                address=incoming.address,
                city=incoming.city,
                state=incoming.state,
                price_min=incoming.price_min,
                price_max=incoming.price_max,
                price_notes=incoming.price_notes,
                ticket_url=incoming.ticket_url,
                source_urls=list(incoming.source_urls),
                created_at=self.now,
                last_verified=self.now,
            )
            series.occurrences.append(occurrence)
            self._locate(occurrence)
            self.report.new_dates.append(
                f"{series.name}: {describe_dates(occurrence.start_date, occurrence.end_date, occurrence.date_status)}"
                f" in {occurrence.city}"
            )
            return

        existing.source_urls = _union(list(existing.source_urls), list(incoming.source_urls))
        existing.last_verified = self.now
        self.report.updated_dates += 1

        if existing.date_status == "confirmed" and incoming.date_status == "estimated":
            # A guess never overwrites announced details; it can only fill gaps.
            for name in ("price_min", "price_max", "price_notes", "ticket_url", "venue_name", "address"):
                if getattr(existing, name) is None:
                    setattr(existing, name, getattr(incoming, name))
        else:
            if existing.date_status == "estimated" and incoming.date_status == "confirmed":
                self.report.newly_confirmed.append(
                    f"{series.name}: {describe_dates(incoming.start_date, incoming.end_date, 'confirmed')}"
                    f" in {incoming.city}"
                )
            existing.start_date = incoming.start_date
            existing.end_date = incoming.end_date
            existing.date_status = incoming.date_status

            place = (
                incoming.venue_name or existing.venue_name,
                incoming.address or existing.address,
                incoming.city,
                incoming.state,
            )
            if place != (existing.venue_name, existing.address, existing.city, existing.state):
                existing.venue_name, existing.address, existing.city, existing.state = place
                existing.lat = existing.lng = None

            for name in ("price_min", "price_max", "price_notes", "ticket_url"):
                value = getattr(incoming, name)
                if value is not None:
                    setattr(existing, name, value)

        if existing.lat is None:
            self._locate(existing)

    def _locate(self, occurrence: EventOccurrence) -> None:
        if self.geocoder is None:
            return
        point = locate(
            self.geocoder,
            venue_name=occurrence.venue_name,
            address=occurrence.address,
            city=occurrence.city,
            state=occurrence.state,
        )
        if point is None:
            return
        occurrence.lat, occurrence.lng = point

    def _retry_missing_locations(self) -> None:
        if self.geocoder is None:
            return
        missing = list(self.session.scalars(select(EventOccurrence).where(EventOccurrence.lat.is_(None))))
        for occurrence in missing:
            touched_this_run = occurrence.last_verified == self.now
            if not touched_this_run:
                # Left over from an earlier import that was offline.
                self._locate(occurrence)
            if occurrence.lat is None and touched_this_run:
                self.report.warnings.append(
                    f"Couldn't locate {occurrence.series.name} ({occurrence.city}, {occurrence.state}); "
                    "its drive time is unknown."
                )


def import_batch(
    session: Session,
    batch: EventBatch,
    *,
    geocoder: Geocoder | None,
    file_name: str | None = None,
    now: datetime | None = None,
) -> ImportReport:
    return Importer(session, geocoder, now=now).run(batch, file_name=file_name)
