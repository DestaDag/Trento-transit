import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.occupancy import decayed_level, resolve_occupancy


def test_seed_contains_at_least_ten_realistic_venues():
    path = Path(__file__).parents[1] / "data" / "trento_study_spots.json"
    spots = json.loads(path.read_text())
    assert len(spots) >= 10
    assert all(spot["lat"] and spot["lon"] for spot in spots)
    assert all(spot["amenities"] for spot in spots)


def test_decay_half_life():
    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    recent = (2, now)
    old = (1, now - timedelta(minutes=45))
    assert decayed_level([recent], now) == 2
    assert decayed_level([recent, old], now) == pytest.approx(1.666667, rel=1e-5)


def test_crowdsourced_resolution_and_closed():
    now = datetime(2026, 11, 26, 7, 0, tzinfo=UTC)
    spot = {
        "hours_json": {
            "thursday": [{"open": "09:00", "close": "18:00"}]
        },
        "capacity_tier": "medium",
    }
    occupancy = resolve_occupancy(spot, [(1, now)], now)
    assert occupancy["status"] == "Closed"