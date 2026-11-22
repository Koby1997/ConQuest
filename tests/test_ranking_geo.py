from datetime import date, datetime

import pytest

from conquest.db import get_settings
from conquest.geo import estimate_drive_minutes, haversine_miles, locate
from conquest.merge import import_batch
from conquest.models import EventSeries
from conquest.ranking import expected_month, learned_category_points, match_score, rank_all
from conquest.schemas import EventBatch

ORLANDO = (28.5384, -81.3789)
TODAY = date(2026, 11, 21)


@pytest.mark.parametrize(
    ("city", "point", "real_minutes"),
    [
        # Typical drive times from downtown Orlando, for checking the estimate.
        ("Tampa", (27.9506, -82.4572), 85),
        ("Jacksonville", (30.3322, -81.6557), 135),
        ("Miami", (25.7617, -80.1918), 215),
    ],
)
def test_drive_estimate_is_close_to_real_drives(city, point, real_minutes):
    estimate = estimate_drive_minutes(*ORLANDO, *point)
    assert abs(estimate - real_minutes) / real_minutes < 0.25, f"{city}: {estimate} vs ~{real_minutes}"


def test_haversine_known_distance():
    # Orlando to Tampa is a little under 80 miles in a straight line.
    assert 72 < haversine_miles(*ORLANDO, 27.9506, -82.4572) < 82


def test_locate_falls_back_to_the_city(geocoder):
    point = locate(geocoder, venue_name="Some Hall", address="1 Main St", city="Tampa", state="FL")
    assert point == (27.9506, -82.4572)


def _series(**fields) -> EventSeries:
    defaults = dict(name="x", categories=["maker"], ai_interest_score=60, rating=0, aliases=[], occurrences=[])
    return EventSeries(**{**defaults, **fields})


def test_thumbs_teach_categories():
    liked = [_series(categories=["maker"], rating=1), _series(categories=["maker", "tech"], rating=1)]
    learned = learned_category_points(liked)

    assert learned["maker"] == pytest.approx(9.0)  # (1 + 1/2) * 6
    assert learned["tech"] == pytest.approx(3.0)

    unrated_maker = _series(categories=["maker"])
    assert match_score(unrated_maker, learned, {}) == 69


def test_own_rating_and_boosts_move_the_score():
    assert match_score(_series(rating=1), {}, {}) == 85
    assert match_score(_series(rating=-1), {}, {}) == 35
    assert match_score(_series(), {}, {"maker": 2}) == 80
    assert match_score(_series(ai_interest_score=95, rating=1), {}, {}) == 100  # clamped


def test_learned_points_are_capped():
    many = [_series(rating=-1) for _ in range(20)]
    assert learned_category_points(many)["maker"] == -30


def test_expected_month_wraps_into_next_year():
    assert expected_month(_series(usual_months=[3, 11], active=True), TODAY) == 11
    assert expected_month(_series(usual_months=[1, 3], active=True), TODAY) == 1
    assert expected_month(_series(usual_months=[1], active=False), TODAY) is None


def test_drive_limit_depends_on_size(session, geocoder):
    raw = {
        "mode": "seed",
        "series": [
            _raw("Local Talk in Tampa", "local", "Tampa"),
            _raw("Regional Show in Jacksonville", "regional", "Jacksonville"),
            _raw("Major Con in Miami", "major", "Miami"),
            _raw("Major Con in Atlanta", "major", "Atlanta", state="GA"),
            _raw("Local Talk in Kissimmee", "local", "Kissimmee"),
        ],
    }
    settings = get_settings(session)
    settings.home_lat, settings.home_lng = ORLANDO
    import_batch(session, EventBatch.model_validate(raw), geocoder=geocoder, now=datetime(2026, 11, 1))
    session.commit()

    ranked = {r.series.name: r for r in rank_all(list(session.query(EventSeries)), get_settings(session), TODAY)}

    assert ranked["Local Talk in Kissimmee"].within_range is True
    assert ranked["Local Talk in Tampa"].within_range is False  # 2 h is too far for a talk
    assert ranked["Regional Show in Jacksonville"].within_range is True
    assert ranked["Major Con in Miami"].within_range is True  # but fine for a big con
    assert ranked["Major Con in Atlanta"].within_range is False


def _raw(name: str, size: str, city: str, state: str = "FL") -> dict:
    return {
        "name": name,
        "categories": ["tech"],
        "size_tier": size,
        "description": "A test event description that is long enough.",
        "ai_interest_score": 50,
        "occurrences": [{"start_date": "2027-03-01", "date_status": "confirmed", "city": city, "state": state}],
    }
