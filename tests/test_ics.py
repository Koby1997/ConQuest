from datetime import date, datetime

from conquest.ics import _escape, _fold, build_calendar
from conquest.models import EventOccurrence, EventSeries


def _occurrence(**fields) -> EventOccurrence:
    series = EventSeries(
        name=fields.pop("name", "Sample Con"),
        description=fields.pop("description", "Comics, cosplay, and more."),
        website="https://example.com/con",
        aliases=[],
        categories=["comic_pop"],
    )
    defaults = dict(
        id=7,
        start_date=date(2027, 5, 20),
        end_date=date(2027, 5, 23),
        date_status="confirmed",
        venue_name="Convention Center",
        address="9800 International Dr, Orlando, FL 32819",
        city="Orlando",
        state="FL",
        price_min=40.0,
        price_max=150.0,
        price_notes=None,
        ticket_url=None,
    )
    occurrence = EventOccurrence(**{**defaults, **fields})
    occurrence.series = series
    return occurrence


def _unfold(text: str) -> str:
    return text.replace("\r\n ", "")


def test_all_day_event_with_exclusive_end():
    text = build_calendar([_occurrence()], now=datetime(2026, 11, 21, 12, 0))

    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20270520\r\n" in text
    assert "DTEND;VALUE=DATE:20270524\r\n" in text  # day after the last day
    assert "UID:conquest-occurrence-7@conquest.local" in text
    assert "STATUS:CONFIRMED" in text
    assert "Tickets: $40-$150" in _unfold(text)


def test_single_day_event_ends_next_day():
    text = build_calendar([_occurrence(end_date=None, start_date=date(2027, 3, 4))])
    assert "DTEND;VALUE=DATE:20270305" in text


def test_estimated_dates_are_labelled_tentative():
    text = _unfold(build_calendar([_occurrence(date_status="estimated")]))

    assert "SUMMARY:Sample Con (estimated dates)" in text
    assert "STATUS:TENTATIVE" in text
    assert "Dates are an estimate" in text


def test_text_is_escaped():
    assert _escape("A, B; C\\D\nE") == "A\\, B\\; C\\\\D\\nE"
    text = _unfold(build_calendar([_occurrence()]))
    assert "LOCATION:Convention Center\\, 9800 International Dr\\, Orlando\\, FL 32819" in text


def test_long_lines_are_folded_to_75_octets():
    long_description = "Robots and rockets " * 20 + "— café ✨"
    text = build_calendar([_occurrence(description=long_description)])

    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    assert long_description.replace(",", "\\,") in _unfold(text)


def test_fold_never_splits_multibyte_characters():
    pieces = _fold("X" * 74 + "é" * 10)
    assert all(len(p.encode("utf-8")) <= 75 for p in pieces)
    assert "".join(p.lstrip(" ") if i else p for i, p in enumerate(pieces)) == "X" * 74 + "é" * 10


def test_events_are_in_date_order():
    later = _occurrence(id=1, start_date=date(2027, 9, 1), end_date=None, name="Later")
    sooner = _occurrence(id=2, start_date=date(2027, 2, 1), end_date=None, name="Sooner")
    text = build_calendar([later, sooner])
    assert text.index("SUMMARY:Sooner") < text.index("SUMMARY:Later")
