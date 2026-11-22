"""The JSON format a /discover session hands to `conquest import`.

Claude does the research; this file decides what counts as usable data. Every
field is checked before anything touches the database, and errors name the
exact field (``series[2].occurrences[0].start_date``) so the session can fix
the file and import it again.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from conquest.categories import CATEGORIES, REGIONS

CategorySlug = Literal[
    "comic_pop",
    "anime_gaming",
    "tech",
    "maker",
    "space_science",
    "engineering",
    "film_music",
    "talks",
    "museum",
    "other",
]
assert set(CategorySlug.__args__) == set(CATEGORIES), "CategorySlug is out of sync with CATEGORIES"

Month = Annotated[int, Field(ge=1, le=12)]
Score = Annotated[int, Field(ge=0, le=100)]


def _check_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        raise ValueError("must be a full http(s) URL")
    return value


def _require_url(value: str) -> str:
    checked = _check_url(value)
    if checked is None:
        raise ValueError("must be a full http(s) URL, not empty")
    return checked


OptionalUrl = Annotated[str | None, AfterValidator(_check_url)]
Url = Annotated[str, AfterValidator(_require_url)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OccurrenceIn(_Strict):
    """One edition of an event: its dates, place and prices."""

    start_date: date
    end_date: date | None = None
    date_status: Literal["confirmed", "estimated"] = Field(
        description="'estimated' when the dates are a guess from past years (shown as a month only)."
    )
    venue_name: str | None = None
    address: str | None = None
    city: str = Field(min_length=2)
    state: str = Field(default="FL", min_length=2, max_length=2)
    price_min: float | None = Field(default=None, ge=0, description="Cheapest ticket in USD; 0 means free.")
    price_max: float | None = Field(default=None, ge=0)
    price_notes: str | None = Field(default=None, description="e.g. '$35 Sat, $85 weekend, kids under 6 free'")
    ticket_url: OptionalUrl = None
    source_urls: list[Url] = Field(default_factory=list)

    @field_validator("state")
    @classmethod
    def _upper_state(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _ranges(self) -> OccurrenceIn:
        if self.end_date and self.end_date < self.start_date:
            raise ValueError(f"end_date {self.end_date} is before start_date {self.start_date}")
        if self.price_min is not None and self.price_max is not None and self.price_max < self.price_min:
            raise ValueError(f"price_max {self.price_max} is less than price_min {self.price_min}")
        return self


class SeriesIn(_Strict):
    """An event that may repeat, plus any editions found for it."""

    matches_existing_series_id: int | None = Field(
        default=None, description="The id from `conquest context` when this is an event the app already knows."
    )
    rename: bool = Field(
        default=False,
        description="True when the event now goes by a new name. The old name is kept as an alias.",
    )
    name: str = Field(min_length=2, max_length=200)
    aliases: list[str] = Field(default_factory=list, description="Former names and common short names.")
    website: OptionalUrl = None
    categories: list[CategorySlug] = Field(min_length=1, max_length=4)
    size_tier: Literal["local", "regional", "major"]
    recurrence: Literal["annual", "multiple_per_year", "one_time", "unknown"] = "annual"
    usual_months: list[Month] = Field(default_factory=list)
    active: bool = Field(default=True, description="False if the event has ended for good.")
    description: str = Field(min_length=20, description="2-4 sentences on what it is and what you do there.")
    review_summary: str | None = Field(
        default=None, description="What past attendees say, in 2-3 sentences. Leave empty if nothing was found."
    )
    review_pros: list[str] = Field(default_factory=list, max_length=6)
    review_cons: list[str] = Field(default_factory=list, max_length=6)
    review_sources: list[Url] = Field(default_factory=list, description="Links to the reviews/threads summarised.")
    ai_interest_score: Score = Field(description="0-100: how well this fits the interest profile.")
    interest_reason: str | None = Field(default=None, max_length=300, description="One line on why it fits (or doesn't).")
    occurrences: list[OccurrenceIn] = Field(default_factory=list)

    @field_validator("aliases")
    @classmethod
    def _clean_aliases(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v and v.strip()]


class ScoreUpdate(_Strict):
    """A new interest score for a known event, from `/discover rescore` or a Ticketmaster review."""

    series_id: int
    ai_interest_score: Score
    interest_reason: str | None = Field(default=None, max_length=300)
    categories: list[CategorySlug] | None = Field(default=None, min_length=1, max_length=4)
    size_tier: Literal["local", "regional", "major"] | None = None


class EventBatch(_Strict):
    """Everything one /discover session found."""

    mode: Literal["seed", "rotation", "category", "refresh", "rescore"]
    categories_searched: list[CategorySlug] = Field(default_factory=list)
    regions_searched: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, description="Anything worth remembering about this session's search.")
    series: list[SeriesIn] = Field(default_factory=list)
    score_updates: list[ScoreUpdate] = Field(default_factory=list)

    @field_validator("regions_searched")
    @classmethod
    def _known_regions(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in REGIONS]
        if unknown:
            raise ValueError(f"unknown region(s) {unknown}; use one of {REGIONS}")
        return values


def format_validation_error(error: ValidationError) -> str:
    """Render pydantic errors as one readable line per problem."""
    lines = []
    for item in error.errors():
        path = ""
        for part in item["loc"]:
            path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
        message = item["msg"]
        if "input" in item and item["type"] not in ("missing", "extra_forbidden"):
            shown = repr(item["input"])
            if len(shown) > 80:
                shown = shown[:77] + "..."
            message += f" (got {shown})"
        lines.append(f"- {path or '(top level)'}: {message}")
    return "\n".join(lines)
