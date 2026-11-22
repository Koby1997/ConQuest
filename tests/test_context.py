from datetime import date, datetime

from conquest.context import build_context, suggest_categories
from conquest.merge import import_batch
from conquest.schemas import EventBatch

TODAY = date(2026, 11, 21)


def test_empty_database_suggests_never_searched_categories(session):
    context = build_context(session, today=TODAY)

    assert context["known_series"] == []
    assert len(context["suggested_next"]["categories"]) == 2
    assert context["home"]["label"]  # seeded from config / .env
    assert context["search_history"]["maker"]["Central Florida"] is None


def test_focus_category_overrides_the_suggestion(session):
    context = build_context(session, today=TODAY, focus_category="space_science")
    assert context["suggested_next"]["categories"] == ["space_science"]


def test_known_series_and_rotation_after_an_import(session, sample_batch):
    import_batch(session, EventBatch.model_validate(sample_batch), geocoder=None, now=datetime(2026, 9, 1))
    session.commit()

    context = build_context(session, today=TODAY)

    names = {entry["name"]: entry for entry in context["known_series"]}
    assert names["Sample Comic Convention"]["next"] == "2027-05-20 (confirmed)"
    assert names["Sample Maker Faire Orlando"]["aka"] == ["SMF Orlando"]
    assert context["search_history"]["maker"]["Central Florida"] == "2026-09-01"

    # Categories never searched anywhere come before ones searched in one region.
    assert context["suggested_next"]["categories"] == ["anime_gaming", "tech"]

    # The maker faire only has an estimated date and was checked > 45 days ago.
    due = [entry["name"] for entry in context["needs_date_check"]]
    assert due == ["Sample Maker Faire Orlando"]


def test_details_include_what_rescoring_needs(session, sample_batch):
    import_batch(session, EventBatch.model_validate(sample_batch), geocoder=None, now=datetime(2026, 9, 1))
    session.commit()

    brief = build_context(session, today=TODAY)["known_series"][0]
    detailed = build_context(session, today=TODAY, details=True)["known_series"][0]

    assert "description" not in brief
    assert detailed["description"].startswith("A large multi-day")
    assert detailed["score"] == 80


def test_rotation_prefers_least_recently_searched():
    history = {
        (category, region): datetime(2026, 11, 1)
        for category in ["comic_pop", "anime_gaming", "tech", "maker", "engineering", "film_music", "talks", "museum"]
        for region in ["Central Florida", "Tampa Bay", "Northeast Florida", "South Florida"]
    }
    history[("tech", "Tampa Bay")] = datetime(2026, 1, 1)

    assert suggest_categories(history) == ["space_science", "tech"]
