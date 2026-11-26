import hashlib
import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_m * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def hash_client_id(client_id: str | None, client_ip: str | None, salt: str) -> str:
    value = client_id or client_ip or "anonymous"
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def decayed_level(reports: list[tuple[int, datetime]], now: datetime) -> float | None:
    weighted = 0.0
    weight = 0.0
    for level, reported_at in reports:
        age_minutes = max(0.0, (now - reported_at).total_seconds() / 60)
        report_weight = 0.5 ** (age_minutes / 45.0)
        weighted += level * report_weight
        weight += report_weight
    if weight == 0:
        return None
    return weighted / weight


def heuristic_occupancy(
    spot: dict[str, Any], now: datetime | None = None
) -> float:
    local = (now or datetime.now(UTC)).astimezone(ROME)
    weekday = local.weekday()
    hour = local.hour + local.minute / 60
    peak = 0.0
    if weekday < 5:
        if 8 <= hour <= 12:
            peak = 0.65
        elif 12 < hour <= 18:
            peak = 0.78
        elif 18 < hour <= 20:
            peak = 0.48
    else:
        peak = 0.38
    capacity = spot.get("capacity_tier", "medium")
    factor = {"small": 1.12, "medium": 1.0, "large": 0.88}.get(str(capacity), 1.0)
    return min(0.95, peak * factor)


def occupancy_label(percent: float) -> str:
    if percent < 0.50:
        return "Available"
    if percent <= 0.80:
        return "Moderate"
    return "Busy"


def is_open(spot: dict[str, Any], now: datetime | None = None) -> bool:
    local = (now or datetime.now(UTC)).astimezone(ROME)
    hours = spot.get("hours_json", spot.get("hours"))
    if isinstance(hours, str):
        import json

        hours = json.loads(hours)
    if not isinstance(hours, dict):
        return False
    day = local.strftime("%A").lower()
    windows = hours.get(day, [])
    if isinstance(windows, dict):
        windows = [windows]
    minutes = local.hour * 60 + local.minute
    for window in windows:
        try:
            start_h, start_m = map(int, window["open"].split(":"))
            end_h, end_m = map(int, window["close"].split(":"))
        except (KeyError, TypeError, ValueError):
            continue
        if start_h * 60 + start_m <= minutes < end_h * 60 + end_m:
            return True
    return False


def resolve_occupancy(
    spot: dict[str, Any],
    reports: list[tuple[int, datetime]],
    now: datetime | None = None,
    live_percent: float | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(UTC)
    if not is_open(spot, current):
        return {
            "status": "Closed",
            "occupancy_percent": None,
            "source": "estimated",
        }
    if live_percent is not None:
        percent = live_percent
        source = "live"
    else:
        averaged = decayed_level(reports, current)
        if averaged is not None:
            percent = (averaged - 1) / 2
            percent = max(0.0, min(1.0, percent))
            source = "crowdsourced"
        else:
            percent = heuristic_occupancy(spot, current)
            source = "estimated"
    return {
        "status": occupancy_label(percent),
        "occupancy_percent": round(percent * 100, 1),
        "source": source,
    }


def rate_limit_window(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    return current - timedelta(minutes=15)