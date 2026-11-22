from datetime import datetime

from sqlalchemy import func, select

from conquest.merge import describe_dates, import_batch, normalize_name
from conquest.models import EventOccurrence, EventSeries, SourceRecord
from conquest.schemas import EventBatch

FIRST = datetime(2026, 11, 1, 12, 0)
SECOND = datetime(2026, 11, 8, 12, 0)


def _import(session, raw, geocoder=None, now=FIRST):
    report = import_batch(session, EventBatch.model_validate(raw), geocoder=geocoder, now=now)
    session.commit()
    return report


def _count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def _series(session, name):
    return session.scalar(select(EventSeries).where(EventSeries.name == name))


def test_first_import_creates_series_dates_and_sources(session, sample_batch, geocoder):
    report = _import(session, sample_batch, geocoder)

    assert report.new_series == ["Sample Maker Faire Orlando", "Sample Comic Convention"]
    assert _count(session, EventSeries) == 2
    assert _count(session, EventOccurrence) == 2
    assert _count(session, SourceRecord) == 2

    maker = _series(session, "Sample Maker Faire Orlando")
    assert maker.categories == ["maker", "engineering"]
    assert maker.occurrences[0].lat is not None  # located via the city fallback


def test_reimporting_the_same_findings_updates_instead_of_duplicating(session, sample_batch, geocoder):
    _import(session, sample_batch, geocoder)
    report = _import(session, sample_batch, geocoder, now=SECOND)

    assert report.new_series == []
    assert len(report.updated_series) == 2
    assert report.new_dates == []
    assert _count(session, EventSeries) == 2
    assert _count(session, EventOccurrence) == 2


def test_name_variants_match_the_same_series(session, sample_batch):
    _import(session, sample_batch)

    variant = sample_batch["series"][0]
    variant["name"] = "Orlando Sample Maker Faire 2027"  # reordered, with a year
    _import(session, {"mode": "rotation", "series": [variant]}, now=SECOND)

    assert _count(session, EventSeries) == 2
    maker = session.get(EventSeries, 1)
    assert maker.name == "Sample Maker Faire Orlando"
    assert "Orlando Sample Maker Faire 2027" in maker.aliases


def test_alias_match_and_rename_keep_history(session, sample_batch):
    _import(session, sample_batch)

    renamed = sample_batch["series"][0]
    renamed.update(name="Central Florida Make Fest", aliases=["SMF Orlando"], rename=True)
    _import(session, {"mode": "refresh", "series": [renamed]}, now=SECOND)

    series = session.get(EventSeries, 1)
    assert series.name == "Central Florida Make Fest"
    assert "Sample Maker Faire Orlando" in series.aliases
    assert _count(session, EventSeries) == 2


def test_explicit_id_wins_over_names(session, sample_batch):
    _import(session, sample_batch)

    update = sample_batch["series"][1]
    update.update(name="Totally Different Name", matches_existing_series_id=2)
    _import(session, {"mode": "refresh", "series": [update]}, now=SECOND)

    assert _count(session, EventSeries) == 2
    assert "Totally Different Name" in session.get(EventSeries, 2).aliases


def test_missing_id_falls_back_to_name_with_a_warning(session, sample_batch):
    _import(session, sample_batch)

    update = sample_batch["series"][1]
    update["matches_existing_series_id"] = 999
    report = _import(session, {"mode": "refresh", "series": [update]}, now=SECOND)

    assert _count(session, EventSeries) == 2
    assert any("999 does not exist" in w for w in report.warnings)


def test_different_events_in_the_same_city_stay_separate(session, sample_batch):
    _import(session, sample_batch)

    other = sample_batch["series"][1]
    other["name"] = "Sample Anime Festival"
    _import(session, {"mode": "rotation", "series": [other]}, now=SECOND)

    assert _count(session, EventSeries) == 3


def test_estimated_dates_are_upgraded_when_announced(session, sample_batch):
    _import(session, sample_batch)

    announced = sample_batch["series"][0]
    announced["occurrences"][0].update(
        start_date="2027-11-20", end_date="2027-11-21", date_status="confirmed", price_min=20
    )
    report = _import(session, {"mode": "refresh", "series": [announced]}, now=SECOND)

    occurrences = session.get(EventSeries, 1).occurrences
    assert len(occurrences) == 1
    assert occurrences[0].date_status == "confirmed"
    assert occurrences[0].start_date.isoformat() == "2027-11-20"
    assert occurrences[0].price_min == 20
    assert report.newly_confirmed and "Nov 20-21, 2027" in report.newly_confirmed[0]


def test_an_estimate_never_overwrites_confirmed_details(session, sample_batch):
    _import(session, sample_batch)

    guess = sample_batch["series"][1]
    guess["occurrences"][0].update(start_date="2027-05-01", end_date=None, date_status="estimated", price_min=1)
    _import(session, {"mode": "refresh", "series": [guess]}, now=SECOND)

    occurrence = session.get(EventSeries, 2).occurrences[0]
    assert occurrence.date_status == "confirmed"
    assert occurrence.start_date.isoformat() == "2027-05-20"
    assert occurrence.price_min == 40


def test_next_years_edition_is_added_alongside(session, sample_batch):
    _import(session, sample_batch)

    next_year = sample_batch["series"][1]
    next_year["occurrences"][0].update(start_date="2028-05-18", end_date="2028-05-21")
    _import(session, {"mode": "refresh", "series": [next_year]}, now=SECOND)

    assert len(session.get(EventSeries, 2).occurrences) == 2


def test_user_fields_survive_imports(session, sample_batch):
    _import(session, sample_batch)
    series = session.get(EventSeries, 1)
    series.rating, series.status, series.notes = 1, "going", "Bring the kids"
    session.commit()

    _import(session, sample_batch, now=SECOND)

    series = session.get(EventSeries, 1)
    assert (series.rating, series.status, series.notes) == (1, "going", "Bring the kids")


def test_score_updates_apply_to_known_series(session, sample_batch):
    _import(session, sample_batch)

    report = _import(
        session,
        {
            "mode": "rescore",
            "score_updates": [
                {"series_id": 1, "ai_interest_score": 40, "interest_reason": "Less relevant now"},
                {"series_id": 42, "ai_interest_score": 10},
            ],
        },
        now=SECOND,
    )

    assert session.get(EventSeries, 1).ai_interest_score == 40
    assert report.score_updates == 1
    assert any("42 does not exist" in w for w in report.warnings)


def test_unlocatable_venues_are_reported(session, sample_batch, geocoder):
    sample_batch["series"][0]["occurrences"][0]["city"] = "Nowhereville"
    report = _import(session, sample_batch, geocoder)

    assert any("Nowhereville" in w for w in report.warnings)


def test_normalize_name():
    assert normalize_name("The MEGACON Orlando 2027!") == "megacon orlando"
    assert normalize_name("Arts & Science Night") == "arts and science night"


def test_describe_dates():
    from datetime import date

    assert describe_dates(date(2027, 5, 20), date(2027, 5, 23), "confirmed") == "May 20-23, 2027"
    assert describe_dates(date(2027, 5, 30), date(2027, 6, 1), "confirmed") == "May 30 - Jun 1, 2027"
    assert describe_dates(date(2027, 1, 15), None, "estimated") == "est. January 2027"
