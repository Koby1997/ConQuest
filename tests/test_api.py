from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from conquest.api import create_app
from conquest.db import get_settings, session_factory
from conquest.merge import import_batch
from conquest.schemas import EventBatch


@pytest.fixture
def client(engine, sample_batch, geocoder):
    session = session_factory(engine)()
    # Measure from Tampa so the Orlando sample events are a real drive away.
    settings = get_settings(session)
    settings.home_label, settings.home_lat, settings.home_lng = "Tampa, FL", 27.9506, -82.4572
    import_batch(session, EventBatch.model_validate(sample_batch), geocoder=geocoder, now=datetime(2026, 11, 1))
    session.commit()
    session.close()
    return TestClient(create_app(engine, geocoder_factory=lambda _session: geocoder))


def test_events_are_ranked_with_drive_times(client):
    events = client.get("/api/events").json()

    assert [e["name"] for e in events] == ["Sample Maker Faire Orlando", "Sample Comic Convention"]
    maker = events[0]
    assert maker["match_score"] == 90
    assert maker["next"]["date_status"] == "estimated"
    assert 70 < maker["drive_minutes"] < 110
    assert maker["within_range"] is True
    assert maker["is_new"] is True


def test_rating_changes_the_order(client):
    client.patch("/api/events/1", json={"rating": -1})
    events = client.get("/api/events").json()

    assert events[0]["name"] == "Sample Comic Convention"


def test_status_and_notes_are_saved(client):
    detail = client.patch("/api/events/2", json={"status": "going", "notes": "Cosplay!"}).json()

    assert detail["status"] == "going"
    assert detail["notes"] == "Cosplay!"
    assert detail["occurrences"][0]["price_max"] == 150


def test_detail_includes_reviews(client):
    detail = client.get("/api/events/1").json()

    assert detail["review_summary"].startswith("Attendees love")
    assert detail["review_sources"] == ["https://example.com/reviews/maker"]


def test_unknown_event_is_404(client):
    assert client.get("/api/events/99").status_code == 404


def test_invalid_status_is_rejected(client):
    assert client.patch("/api/events/1", json={"status": "maybe"}).status_code == 422


def test_mark_seen_clears_new_badges(client):
    client.post("/api/events/mark-seen")
    assert not any(e["is_new"] for e in client.get("/api/events").json())


def test_settings_round_trip(client):
    updated = client.put(
        "/api/settings",
        json={
            "drive_limits": {"regional": 200},
            "interest_profile": "Rockets and robots.",
            "category_boosts": {"maker": 5, "tech": 0},
        },
    ).json()

    assert updated["drive_limits"] == {"local": 60, "regional": 200, "major": 270}
    assert updated["interest_profile"] == "Rockets and robots."
    assert updated["category_boosts"] == {"maker": 2}  # clamped, zeros dropped


def test_changing_home_geocodes_it(client):
    updated = client.put("/api/settings", json={"home_label": "Miami, FL"}).json()
    assert (updated["home_lat"], updated["home_lng"]) == (25.7617, -80.1918)

    # Now Orlando events are much further away.
    maker = client.get("/api/events").json()[0]
    assert maker["drive_minutes"] > 180


def test_unknown_home_is_rejected(client):
    response = client.put("/api/settings", json={"home_label": "Atlantis"})
    assert response.status_code == 422
    assert "Couldn't find" in response.json()["detail"]


def test_unknown_boost_category_is_rejected(client):
    assert client.put("/api/settings", json={"category_boosts": {"cooking": 1}}).status_code == 422


def test_calendar_lists_every_edition_with_status(client):
    client.patch("/api/events/2", json={"status": "going"})
    entries = client.get("/api/calendar").json()

    assert [e["name"] for e in entries] == ["Sample Comic Convention", "Sample Maker Faire Orlando"]
    comic = entries[0]
    assert comic["start_date"] == "2027-05-20"
    assert comic["status"] == "going"
    assert comic["within_range"] is True


def test_event_ics_download(client):
    response = client.get("/api/events/2/calendar.ics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert 'filename="sample-comic-convention.ics"' in response.headers["content-disposition"]
    assert "SUMMARY:Sample Comic Convention" in response.text


def test_my_calendar_only_includes_chosen_events(client):
    assert client.get("/api/calendar/mine.ics").status_code == 404

    client.patch("/api/events/1", json={"status": "interested"})
    text = client.get("/api/calendar/mine.ics").text

    assert "Sample Maker Faire Orlando" in text
    assert "Sample Comic Convention" not in text


def test_runs_and_meta(client):
    runs = client.get("/api/runs").json()
    assert runs[0]["mode"] == "seed"
    assert runs[0]["new_series"] == 2

    meta = client.get("/api/meta").json()
    assert meta["total_events"] == 2
    assert "maker" in meta["categories"]
