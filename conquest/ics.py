"""iCalendar (.ics) export, for adding events to Google Calendar, Outlook or a phone.

Events are written as all-day entries (conventions run all day, and times are
rarely published far ahead). Estimated dates are exported too, but marked
TENTATIVE and labelled in the title so they aren't mistaken for real ones.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from conquest.models import EventOccurrence, utcnow

PRODUCT_ID = "-//ConQuest//Event Finder//EN"
MAX_LINE_OCTETS = 75


def _escape(text: str) -> str:
    """Escape TEXT values per RFC 5545 section 3.3.11."""
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Split a content line into <=75-octet pieces without breaking a UTF-8 character."""
    pieces: list[str] = []
    current, size = "", 0
    limit = MAX_LINE_OCTETS
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            pieces.append(current)
            # Continuation lines start with a space, which counts toward the limit.
            current, size, limit = char, width, MAX_LINE_OCTETS - 1
        else:
            current += char
            size += width
    pieces.append(current)
    return [pieces[0]] + [" " + piece for piece in pieces[1:]]


def _date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _price_text(occurrence: EventOccurrence) -> str | None:
    low, high = occurrence.price_min, occurrence.price_max
    if low is None and high is None:
        return occurrence.price_notes
    if low == 0 and not high:
        text = "Free"
    elif low is not None and high is not None and high != low:
        text = f"${low:g}-${high:g}"
    else:
        text = f"${(low if low is not None else high):g}"
    return f"{text} ({occurrence.price_notes})" if occurrence.price_notes else text


def event_lines(occurrence: EventOccurrence, *, stamp: datetime) -> list[str]:
    series = occurrence.series
    estimated = occurrence.date_status == "estimated"
    title = series.name + (" (estimated dates)" if estimated else "")

    place = ", ".join(part for part in (occurrence.venue_name, occurrence.address) if part)
    if not place:
        place = f"{occurrence.city}, {occurrence.state}"

    details = [series.description]
    price = _price_text(occurrence)
    if price:
        details.append(f"Tickets: {price}")
    if estimated:
        details.append("Dates are an estimate from past years. Check before booking anything.")
    link = occurrence.ticket_url or series.website
    if link:
        details.append(link)

    lines = [
        "BEGIN:VEVENT",
        f"UID:conquest-occurrence-{occurrence.id}@conquest.local",
        f"DTSTAMP:{_stamp(stamp)}",
        f"DTSTART;VALUE=DATE:{_date(occurrence.start_date)}",
        # All-day DTEND is exclusive: the day after the last day.
        f"DTEND;VALUE=DATE:{_date(occurrence.last_day + timedelta(days=1))}",
        f"SUMMARY:{_escape(title)}",
        f"LOCATION:{_escape(place)}",
        f"DESCRIPTION:{_escape(chr(10).join(details))}",
        f"STATUS:{'TENTATIVE' if estimated else 'CONFIRMED'}",
        "TRANSP:TRANSPARENT",
    ]
    if link:
        lines.append(f"URL:{link}")
    lines.append("END:VEVENT")
    return lines


def build_calendar(
    occurrences: Iterable[EventOccurrence],
    *,
    name: str = "ConQuest",
    now: datetime | None = None,
) -> str:
    stamp = now or utcnow()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODUCT_ID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for occurrence in sorted(occurrences, key=lambda o: o.start_date):
        lines.extend(event_lines(occurrence, stamp=stamp))
    lines.append("END:VCALENDAR")

    folded = [piece for line in lines for piece in _fold(line)]
    return "\r\n".join(folded) + "\r\n"
