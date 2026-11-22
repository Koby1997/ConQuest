from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from conquest.db import make_engine, session_factory

FIXTURES = Path(__file__).parent / "fixtures"

# Real-ish coordinates so drive times are meaningful.
CITY_POINTS = {
    "orlando, fl": (28.5384, -81.3789),
    "tampa, fl": (27.9506, -82.4572),
    "jacksonville, fl": (30.3322, -81.6557),
    "miami, fl": (25.7617, -80.1918),
    "kissimmee, fl": (28.2920, -81.4076),
    "atlanta, ga": (33.7490, -84.3880),
}


class FakeGeocoder:
    """Resolves only the trailing 'City, ST' of a query, and records every call."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def geocode(self, query: str) -> tuple[float, float] | None:
        self.calls.append(query)
        key = ", ".join(part.strip() for part in query.lower().split(",")[-2:])
        return CITY_POINTS.get(key)


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path / "test.db")


@pytest.fixture
def session(engine):
    session = session_factory(engine)()
    yield session
    session.close()


@pytest.fixture
def geocoder():
    return FakeGeocoder()


@pytest.fixture
def sample_batch() -> dict:
    """A fresh, mutable copy of the sample findings file for each test."""
    return copy.deepcopy(json.loads((FIXTURES / "sample_batch.json").read_text(encoding="utf-8")))
