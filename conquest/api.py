"""HTTP API behind the web UI.

Everything here reads and edits the local database. Finding new events is
done by the /discover skill in Claude Code, not by this server.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from conquest.categories import (
    CATEGORIES,
    DEFAULT_DRIVE_LIMITS,
    RECURRENCES,
    REGIONS,
    SIZE_TIERS,
    STATUSES,
)
from conquest.db import get_settings, make_engine, session_factory
from conquest.geo import Geocoder, NominatimGeocoder, estimate_drive_minutes
from conquest.ics import build_calendar
from conquest.models import DiscoveryRun, EventOccurrence, EventSeries, Settings, utcnow
from conquest.ranking import RankedEvent, learned_category_points, rank_all, rank_series

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# Events "on my calendar": the ones marked Interested or Going.
CHOSEN_STATUSES = ("interested", "going")


# --- Response and request bodies -------------------------------------------------


class OccurrenceOut(BaseModel):
    id: int
    start_date: date
    end_date: date | None
    date_status: str
    venue_name: str | None
    address: str | None
    city: str
    state: str
    price_min: float | None
    price_max: float | None
    price_notes: str | None
    ticket_url: str | None
    source_urls: list[str]
    drive_minutes: int | None
    last_verified: datetime | None


class EventCard(BaseModel):
    id: int
    name: str
    aliases: list[str]
    categories: list[str]
    size_tier: str
    recurrence: str
    usual_months: list[int]
    active: bool
    description: str
    website: str | None
    ai_interest_score: int | None
    interest_reason: str | None
    match_score: int
    rating: int
    status: str
    notes: str
    is_new: bool
    first_seen: datetime
    next: OccurrenceOut | None
    expected_month: int | None
    drive_minutes: int | None
    drive_limit: int
    within_range: bool | None
    has_reviews: bool


class EventDetail(EventCard):
    review_summary: str | None
    review_pros: list[str]
    review_cons: list[str]
    review_sources: list[str]
    occurrences: list[OccurrenceOut]
    last_checked: datetime | None


class EventUpdate(BaseModel):
    rating: Literal[-1, 0, 1] | None = None
    status: Literal["none", "interested", "going", "went", "skip"] | None = None
    notes: str | None = Field(default=None, max_length=5000)


class SettingsOut(BaseModel):
    home_label: str
    home_lat: float
    home_lng: float
    drive_limits: dict[str, int]
    interest_profile: str
    category_boosts: dict[str, int]
    learned_category_points: dict[str, float]
    last_seen_new_at: datetime | None


class SettingsIn(BaseModel):
    home_label: str | None = Field(default=None, min_length=2, max_length=200)
    home_lat: float | None = Field(default=None, ge=-90, le=90)
    home_lng: float | None = Field(default=None, ge=-180, le=180)
    drive_limits: dict[Literal["local", "regional", "major"], int] | None = None
    interest_profile: str | None = Field(default=None, max_length=5000)
    category_boosts: dict[str, int] | None = None


class RunOut(BaseModel):
    id: int
    mode: str
    source: str
    categories: list[str]
    regions: list[str]
    notes: str | None
    new_series: int
    updated_series: int
    new_occurrences: int
    updated_occurrences: int
    created_at: datetime


class CalendarEntry(BaseModel):
    """One edition of one event, flattened for drawing on a calendar."""

    occurrence_id: int
    series_id: int
    name: str
    categories: list[str]
    size_tier: str
    status: str
    rating: int
    match_score: int
    active: bool
    start_date: date
    end_date: date | None
    date_status: str
    venue_name: str | None
    city: str
    state: str
    price_min: float | None
    price_max: float | None
    drive_minutes: int | None
    within_range: bool | None


class Meta(BaseModel):
    categories: dict[str, str]
    size_tiers: dict[str, str]
    regions: list[str]
    statuses: dict[str, str]
    recurrences: dict[str, str]
    total_events: int


# --- Conversions ------------------------------------------------------------------


def _occurrence_out(occurrence: EventOccurrence, settings: Settings) -> OccurrenceOut:
    drive = None
    if occurrence.lat is not None and occurrence.lng is not None:
        drive = estimate_drive_minutes(settings.home_lat, settings.home_lng, occurrence.lat, occurrence.lng)
    return OccurrenceOut(
        id=occurrence.id,
        start_date=occurrence.start_date,
        end_date=occurrence.end_date,
        date_status=occurrence.date_status,
        venue_name=occurrence.venue_name,
        address=occurrence.address,
        city=occurrence.city,
        state=occurrence.state,
        price_min=occurrence.price_min,
        price_max=occurrence.price_max,
        price_notes=occurrence.price_notes,
        ticket_url=occurrence.ticket_url,
        source_urls=list(occurrence.source_urls or []),
        drive_minutes=drive,
        last_verified=occurrence.last_verified,
    )


def _card_fields(ranked: RankedEvent, settings: Settings) -> dict:
    series = ranked.series
    return {
        "id": series.id,
        "name": series.name,
        "aliases": list(series.aliases or []),
        "categories": list(series.categories or []),
        "size_tier": series.size_tier,
        "recurrence": series.recurrence,
        "usual_months": list(series.usual_months or []),
        "active": series.active,
        "description": series.description,
        "website": series.website,
        "ai_interest_score": series.ai_interest_score,
        "interest_reason": series.interest_reason,
        "match_score": ranked.match_score,
        "rating": series.rating,
        "status": series.status,
        "notes": series.notes,
        "is_new": ranked.is_new,
        "first_seen": series.first_seen,
        "next": _occurrence_out(ranked.next_occurrence, settings) if ranked.next_occurrence else None,
        "expected_month": ranked.expected_month,
        "drive_minutes": ranked.drive_minutes,
        "drive_limit": ranked.drive_limit,
        "within_range": ranked.within_range,
        "has_reviews": bool(series.review_summary),
    }


def _detail(series: EventSeries, session: Session) -> EventDetail:
    settings = get_settings(session)
    all_series = list(session.scalars(select(EventSeries)))
    ranked = rank_series(series, settings, learned_category_points(all_series), date.today())
    return EventDetail(
        **_card_fields(ranked, settings),
        review_summary=series.review_summary,
        review_pros=list(series.review_pros or []),
        review_cons=list(series.review_cons or []),
        review_sources=list(series.review_sources or []),
        occurrences=[_occurrence_out(o, settings) for o in series.occurrences],
        last_checked=series.last_checked,
    )


def _ics_response(text: str, file_stem: str) -> Response:
    slug = re.sub(r"[^a-z0-9]+", "-", file_stem.lower()).strip("-") or "conquest"
    return Response(
        content=text,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )


def _settings_out(settings: Settings, session: Session) -> SettingsOut:
    all_series = list(session.scalars(select(EventSeries)))
    return SettingsOut(
        home_label=settings.home_label,
        home_lat=settings.home_lat,
        home_lng=settings.home_lng,
        drive_limits={**DEFAULT_DRIVE_LIMITS, **(settings.drive_limits or {})},
        interest_profile=settings.interest_profile,
        category_boosts=dict(settings.category_boosts or {}),
        learned_category_points={k: round(v, 1) for k, v in learned_category_points(all_series).items()},
        last_seen_new_at=settings.last_seen_new_at,
    )


# --- App --------------------------------------------------------------------------


def create_app(engine: Engine | None = None, *, geocoder_factory=None) -> FastAPI:
    engine = engine or make_engine()
    make_session = session_factory(engine)
    # Only used when the home location is changed in Settings.
    make_geocoder = geocoder_factory or (lambda session: NominatimGeocoder(session))

    def get_session() -> Iterator[Session]:
        session = make_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = FastAPI(title="ConQuest", description="Find fun events before they happen.", version="0.1.0")

    # The dev frontend runs on a different port under Vite.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/meta", response_model=Meta)
    def meta(session: Session = Depends(get_session)) -> Meta:
        total = len(list(session.scalars(select(EventSeries.id))))
        return Meta(
            categories=CATEGORIES,
            size_tiers=SIZE_TIERS,
            regions=REGIONS,
            statuses=STATUSES,
            recurrences=RECURRENCES,
            total_events=total,
        )

    @app.get("/api/events", response_model=list[EventCard])
    def list_events(session: Session = Depends(get_session)) -> list[EventCard]:
        settings = get_settings(session)
        all_series = list(session.scalars(select(EventSeries)))
        return [EventCard(**_card_fields(r, settings)) for r in rank_all(all_series, settings, date.today())]

    @app.get("/api/events/{series_id}", response_model=EventDetail)
    def get_event(series_id: int, session: Session = Depends(get_session)) -> EventDetail:
        series = session.get(EventSeries, series_id)
        if series is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return _detail(series, session)

    @app.patch("/api/events/{series_id}", response_model=EventDetail)
    def update_event(series_id: int, body: EventUpdate, session: Session = Depends(get_session)) -> EventDetail:
        series = session.get(EventSeries, series_id)
        if series is None:
            raise HTTPException(status_code=404, detail="Event not found")
        if body.rating is not None:
            series.rating = body.rating
        if body.status is not None:
            series.status = body.status
        if body.notes is not None:
            series.notes = body.notes
        session.flush()
        return _detail(series, session)

    @app.get("/api/events/{series_id}/calendar.ics")
    def event_ics(series_id: int, session: Session = Depends(get_session)) -> Response:
        series = session.get(EventSeries, series_id)
        if series is None:
            raise HTTPException(status_code=404, detail="Event not found")
        upcoming = [o for o in series.occurrences if o.last_day >= date.today()]
        if not upcoming:
            raise HTTPException(status_code=404, detail="This event has no upcoming dates to add yet.")
        return _ics_response(build_calendar(upcoming, name=series.name), series.name)

    @app.get("/api/calendar", response_model=list[CalendarEntry])
    def calendar(session: Session = Depends(get_session)) -> list[CalendarEntry]:
        settings = get_settings(session)
        all_series = list(session.scalars(select(EventSeries)))
        entries = []
        for ranked in rank_all(all_series, settings, date.today()):
            series = ranked.series
            for occurrence in series.occurrences:
                drive = None
                if occurrence.lat is not None and occurrence.lng is not None:
                    drive = estimate_drive_minutes(
                        settings.home_lat, settings.home_lng, occurrence.lat, occurrence.lng
                    )
                entries.append(
                    CalendarEntry(
                        occurrence_id=occurrence.id,
                        series_id=series.id,
                        name=series.name,
                        categories=list(series.categories or []),
                        size_tier=series.size_tier,
                        status=series.status,
                        rating=series.rating,
                        match_score=ranked.match_score,
                        active=series.active,
                        start_date=occurrence.start_date,
                        end_date=occurrence.end_date,
                        date_status=occurrence.date_status,
                        venue_name=occurrence.venue_name,
                        city=occurrence.city,
                        state=occurrence.state,
                        price_min=occurrence.price_min,
                        price_max=occurrence.price_max,
                        drive_minutes=drive,
                        within_range=None if drive is None else drive <= ranked.drive_limit,
                    )
                )
        entries.sort(key=lambda e: (e.start_date, e.name.lower()))
        return entries

    @app.get("/api/calendar/mine.ics")
    def my_calendar_ics(session: Session = Depends(get_session)) -> Response:
        chosen = session.scalars(select(EventSeries).where(EventSeries.status.in_(CHOSEN_STATUSES)))
        upcoming = [o for s in chosen for o in s.occurrences if o.last_day >= date.today()]
        if not upcoming:
            raise HTTPException(
                status_code=404,
                detail="Nothing on your calendar yet. Add events with the 📅 button first.",
            )
        return _ics_response(build_calendar(upcoming, name="ConQuest - My events"), "conquest-my-events")

    @app.post("/api/events/mark-seen", response_model=SettingsOut)
    def mark_seen(session: Session = Depends(get_session)) -> SettingsOut:
        settings = get_settings(session)
        settings.last_seen_new_at = utcnow()
        session.flush()
        return _settings_out(settings, session)

    @app.get("/api/settings", response_model=SettingsOut)
    def read_settings(session: Session = Depends(get_session)) -> SettingsOut:
        return _settings_out(get_settings(session), session)

    @app.put("/api/settings", response_model=SettingsOut)
    def write_settings(body: SettingsIn, session: Session = Depends(get_session)) -> SettingsOut:
        settings = get_settings(session)

        if body.home_lat is not None and body.home_lng is not None:
            settings.home_lat, settings.home_lng = body.home_lat, body.home_lng
            if body.home_label:
                settings.home_label = body.home_label
        elif body.home_label and body.home_label != settings.home_label:
            geocoder: Geocoder = make_geocoder(session)
            point = geocoder.geocode(body.home_label)
            if point is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"Couldn't find {body.home_label!r}. Try 'City, ST', e.g. 'Orlando, FL'.",
                )
            settings.home_label = body.home_label
            settings.home_lat, settings.home_lng = point

        if body.drive_limits is not None:
            limits = {**DEFAULT_DRIVE_LIMITS, **(settings.drive_limits or {})}
            for tier, minutes in body.drive_limits.items():
                if not 10 <= minutes <= 24 * 60:
                    raise HTTPException(status_code=422, detail=f"Drive limit for {tier} must be 10-1440 minutes.")
                limits[tier] = minutes
            settings.drive_limits = limits

        if body.interest_profile is not None:
            settings.interest_profile = body.interest_profile.strip()

        if body.category_boosts is not None:
            unknown = set(body.category_boosts) - set(CATEGORIES)
            if unknown:
                raise HTTPException(status_code=422, detail=f"Unknown categories: {sorted(unknown)}")
            settings.category_boosts = {
                c: max(-2, min(2, int(v))) for c, v in body.category_boosts.items() if int(v) != 0
            }

        session.flush()
        return _settings_out(settings, session)

    @app.get("/api/runs", response_model=list[RunOut])
    def list_runs(session: Session = Depends(get_session)) -> list[RunOut]:
        runs = session.scalars(select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(100))
        return [RunOut.model_validate(run, from_attributes=True) for run in runs]

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


def __getattr__(name: str):
    # `uvicorn conquest.api:app` asks for `app`; build it on first use so that
    # importing this module (e.g. in tests) doesn't create the real database.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
