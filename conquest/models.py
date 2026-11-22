"""Database tables.

The central idea is the split between an event *series* and its
*occurrences*. "MegaCon Orlando" is one series that happens every year; each
year's dates and venue are an occurrence. Knowing the series is what lets the
app say "usually in May" before next year's dates are announced, and keeps a
renamed event's history attached to it through its aliases.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class EventSeries(Base):
    __tablename__ = "event_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    website: Mapped[str | None] = mapped_column(String(500), default=None)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    size_tier: Mapped[str] = mapped_column(String(20), default="regional")
    recurrence: Mapped[str] = mapped_column(String(30), default="annual")
    usual_months: Mapped[list[int]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str] = mapped_column(Text, default="")

    review_summary: Mapped[str | None] = mapped_column(Text, default=None)
    review_pros: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_cons: Mapped[list[str]] = mapped_column(JSON, default=list)
    review_sources: Mapped[list[str]] = mapped_column(JSON, default=list)

    ai_interest_score: Mapped[int | None] = mapped_column(Integer, default=None)
    interest_reason: Mapped[str | None] = mapped_column(Text, default=None)

    # Set only by the person using the app; imports never touch these.
    rating: Mapped[int] = mapped_column(Integer, default=0)  # -1, 0, +1
    status: Mapped[str] = mapped_column(String(20), default="none")
    notes: Mapped[str] = mapped_column(Text, default="")

    # Ticketmaster events arrive without categories or a score until the next
    # /discover run reviews them.
    needs_ai_review: Mapped[bool] = mapped_column(default=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    occurrences: Mapped[list[EventOccurrence]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
        order_by="EventOccurrence.start_date",
    )


class EventOccurrence(Base):
    __tablename__ = "event_occurrence"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("event_series.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    # "estimated" means a best guess from past years (shown as a month only).
    date_status: Mapped[str] = mapped_column(String(20), default="confirmed")

    venue_name: Mapped[str | None] = mapped_column(String(200), default=None)
    address: Mapped[str | None] = mapped_column(String(300), default=None)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2), default="FL")
    lat: Mapped[float | None] = mapped_column(Float, default=None)
    lng: Mapped[float | None] = mapped_column(Float, default=None)

    price_min: Mapped[float | None] = mapped_column(Float, default=None)
    price_max: Mapped[float | None] = mapped_column(Float, default=None)
    price_notes: Mapped[str | None] = mapped_column(Text, default=None)

    ticket_url: Mapped[str | None] = mapped_column(String(500), default=None)
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    series: Mapped[EventSeries] = relationship(back_populates="occurrences")

    @property
    def last_day(self) -> date:
        return self.end_date or self.start_date


class DiscoveryRun(Base):
    """One import from a /discover session (or a Ticketmaster pull)."""

    __tablename__ = "discovery_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(30), default="claude_research")
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    file_name: Mapped[str | None] = mapped_column(String(300), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    new_series: Mapped[int] = mapped_column(Integer, default=0)
    updated_series: Mapped[int] = mapped_column(Integer, default=0)
    new_occurrences: Mapped[int] = mapped_column(Integer, default=0)
    updated_occurrences: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SourceRecord(Base):
    """The raw data each series was built from, kept for traceability."""

    __tablename__ = "source_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int | None] = mapped_column(ForeignKey("event_series.id"), default=None)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("discovery_run.id"), default=None)
    source: Mapped[str] = mapped_column(String(30))
    raw: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Settings(Base):
    """A single row of personal settings, edited in the Settings tab."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    home_label: Mapped[str] = mapped_column(String(200))
    home_lat: Mapped[float] = mapped_column(Float)
    home_lng: Mapped[float] = mapped_column(Float)
    drive_limits: Mapped[dict[str, int]] = mapped_column(JSON)
    interest_profile: Mapped[str] = mapped_column(Text)
    # Manual nudges per category, -2..+2, set in Settings.
    category_boosts: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    last_seen_new_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    query: Mapped[str] = mapped_column(String(400), primary_key=True)
    lat: Mapped[float | None] = mapped_column(Float, default=None)
    lng: Mapped[float | None] = mapped_column(Float, default=None)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Location(Base):
    """A place to plan a trip to later (e.g. "Atlanta, 2027"). Not in the UI yet."""

    __tablename__ = "location"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    radius_minutes: Mapped[int] = mapped_column(Integer, default=60)
    target_date: Mapped[date | None] = mapped_column(Date, default=None)
    notes: Mapped[str] = mapped_column(Text, default="")
