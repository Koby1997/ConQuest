"""Where venues are, and roughly how long the drive is.

Venue coordinates come from OpenStreetMap's Nominatim service. It's free and
needs no key, but its usage policy allows one request per second and asks for
an identifying User-Agent, and every answer is cached in the database so each
venue is looked up only once.

Drive time is an estimate from straight-line distance. No routing service is
called, so the home location never leaves this computer. Checked against real
Florida drives (Orlando to Tampa ~1 h 25, Jacksonville ~2 h 15, Miami ~3 h 30),
it is typically within 10-20%, which is enough to sort "an easy day trip" from
"a weekend with a hotel".
"""

from __future__ import annotations

import math
import time
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from conquest.models import GeocodeCache, utcnow

EARTH_RADIUS_MILES = 3958.8

# Roads are longer than a straight line; Florida's interstates are fairly
# direct, so the factor is modest.
ROAD_FACTOR = 1.15
AVERAGE_MPH = 62
# Getting out of town and parking at the far end.
FIXED_OVERHEAD_MINUTES = 5

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "ConQuest/0.1 (personal event finder)"
MAX_NETWORK_ERRORS = 3


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def estimate_drive_minutes(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    miles = haversine_miles(lat1, lng1, lat2, lng2)
    if miles < 1:
        return FIXED_OVERHEAD_MINUTES
    return round(miles * ROAD_FACTOR / AVERAGE_MPH * 60 + FIXED_OVERHEAD_MINUTES)


class Geocoder(Protocol):
    def geocode(self, query: str) -> tuple[float, float] | None: ...


class NominatimGeocoder:
    """Looks places up on Nominatim, caching every answer (including misses)."""

    def __init__(self, session: Session, *, client: httpx.Client | None = None) -> None:
        self._session = session
        self._client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
        )
        self._last_request = 0.0
        self.network_errors = 0

    def geocode(self, query: str) -> tuple[float, float] | None:
        key = " ".join(query.lower().split())
        cached = self._session.get(GeocodeCache, key)
        if cached is not None:
            if cached.lat is None or cached.lng is None:
                return None
            return cached.lat, cached.lng

        # Offline: stop after a few failures rather than waiting out every timeout.
        if self.network_errors >= MAX_NETWORK_ERRORS:
            return None

        # Respect the one-request-per-second policy.
        wait = 1.0 - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

        try:
            response = self._client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            )
            response.raise_for_status()
            results = response.json()
        except (httpx.HTTPError, ValueError):
            # Don't cache network failures; the next import will retry.
            self.network_errors += 1
            return None

        point = None
        if results:
            point = float(results[0]["lat"]), float(results[0]["lon"])

        self._session.add(
            GeocodeCache(
                query=key,
                lat=point[0] if point else None,
                lng=point[1] if point else None,
                fetched_at=utcnow(),
            )
        )
        self._session.flush()
        return point


def locate(
    geocoder: Geocoder,
    *,
    venue_name: str | None,
    address: str | None,
    city: str,
    state: str,
) -> tuple[float, float] | None:
    """Find a venue, falling back from the most specific description to the city."""
    attempts = []
    if address:
        # Addresses usually already include the city; add it if not.
        attempts.append(address if city.lower() in address.lower() else f"{address}, {city}, {state}")
    if venue_name:
        attempts.append(f"{venue_name}, {city}, {state}")
    attempts.append(f"{city}, {state}")

    for query in attempts:
        point = geocoder.geocode(query)
        if point is not None:
            return point
    return None
