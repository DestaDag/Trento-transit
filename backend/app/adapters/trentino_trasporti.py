import re
from datetime import UTC, datetime
from typing import Any

import httpx


def utc_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_dotnet_date(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r"/Date\((-?\d+)(?:[+-]\d+)?\)/", str(value))
    if not match:
        return None
    seconds = int(match.group(1))
    if abs(seconds) > 10_000_000_000:
        seconds /= 1000
    return datetime.fromtimestamp(seconds, tz=UTC)


def normalize_route_color(route_color: str | None, route_type: int | None) -> str:
    if route_color:
        value = route_color.strip()
        if not value.startswith("#"):
            value = "#" + value
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            return value.upper()
    return {2: "#7B1FA2", 3: "#1976D2", 5: "#D32F2F"}.get(route_type, "#455A64")


class TrentinoTrasportiAdapter:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        requested_with: str = "it.tndigit.mit",
        timeout: float = 4.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.requested_with = requested_with
        self.timeout = timeout
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {"X-Requested-With": self.requested_with}

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.username, self.password)

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if self._client is not None:
            response = await self._client.get(
                f"{self.base_url}{path}", params=params, headers=self._headers()
            )
        else:
            async with httpx.AsyncClient(
                http2=True,
                timeout=self.timeout,
                auth=self._auth(),
            ) as client:
                response = await client.get(
                    f"{self.base_url}{path}", params=params, headers=self._headers()
                )
        response.raise_for_status()
        return response.json()

    async def get_stops(self, stop_type: str = "U") -> list[dict[str, Any]]:
        payload = await self._get("/stops", {"type": stop_type})
        items = payload if isinstance(payload, list) else payload.get("stops", payload)
        if not isinstance(items, list):
            items = []
        return [normalize_stop(item) for item in items]

    async def get_routes(self, areas: str = "23,7,8") -> list[dict[str, Any]]:
        payload = await self._get("/routes", {"areas": areas})
        items = payload if isinstance(payload, list) else payload.get("routes", payload)
        if not isinstance(items, list):
            items = []
        return [normalize_route(item) for item in items]

    async def get_trips_new(
        self, stop_id: str, stop_type: str = "U", limit: int = 5,
        ref_date_time: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"stopId": stop_id, "type": stop_type, "limit": limit}
        if ref_date_time:
            params["refDateTime"] = ref_date_time
        payload = await self._get("/trips_new", params)
        items = payload if isinstance(payload, list) else payload.get("trips", payload)
        if not isinstance(items, list):
            items = []
        normalized = [normalize_trip(item) for item in items]
        now = datetime.now(tz=UTC)
        normalized = [
            trip for trip in normalized
            if (trip["effective_arrival"] or trip["scheduled_arrival"]) is None
            or ((trip["effective_arrival"] or trip["scheduled_arrival"]) - now).total_seconds() >= -60
        ]
        normalized.sort(
            key=lambda trip: trip["effective_arrival"] or trip["scheduled_arrival"] or now
        )
        return normalized[:limit]

    async def get_trip(self, trip_id: str) -> dict[str, Any]:
        payload = await self._get(f"/trips/{trip_id}")
        return normalize_trip(payload)

    async def get_bikesharing(self) -> list[dict[str, Any]]:
        payload = await self._get("/poi/bikesharing")
        items = payload if isinstance(payload, list) else payload.get("pois", payload)
        if not isinstance(items, list):
            items = []
        return [normalize_bikesharing(item) for item in items]


def normalize_stop(item: dict[str, Any]) -> dict[str, Any]:
    routes = item.get("routes") or []
    return {
        "stop_id": str(item.get("stopId") or item.get("stop_id")),
        "stop_code": item.get("stopCode"),
        "stop_name": item.get("stopName") or item.get("stop_name") or "",
        "stop_lat": float(item["stopLat"]),
        "stop_lon": float(item["stopLon"]),
        "wheelchair_boarding": int(item.get("wheelchairBoarding") or 0),
        "routes": routes,
    }


def normalize_route(item: dict[str, Any]) -> dict[str, Any]:
    route_type = item.get("routeType")
    active_news = []
    now = datetime.now(tz=UTC)
    for notice in item.get("news") or []:
        start = parse_dotnet_date(notice.get("startDate"))
        end = parse_dotnet_date(notice.get("endDate"))
        if (start is None or start <= now) and (end is None or end >= now):
            active_news.append({
                "header": notice.get("header"),
                "details": notice.get("details"),
                "url": notice.get("url"),
                "start_date": start,
                "end_date": end,
            })
    return {
        "route_id": str(item.get("routeId") or item.get("route_id")),
        "area_id": str(item.get("areaId")) if item.get("areaId") is not None else None,
        "short_name": item.get("routeShortName") or item.get("short_name"),
        "long_name": item.get("routeLongName") or item.get("long_name"),
        "route_type": int(route_type) if route_type is not None else None,
        "route_color": normalize_route_color(item.get("routeColor"), route_type),
        "news": active_news,
    }


def normalize_trip(item: dict[str, Any]) -> dict[str, Any]:
    scheduled = utc_iso(
        item.get("oraArrivoProgrammataAFermataSelezionata")
    )
    effective = utc_iso(
        item.get("oraArrivoEffettivaAFermataSelezionata")
    )
    delay = item.get("delay")
    last_event = item.get("lastEventRecivedAt")
    return {
        "trip_id": str(item.get("tripId") or item.get("trip_id")),
        "route_id": str(item.get("routeId")) if item.get("routeId") is not None else None,
        "trip_headsign": item.get("tripHeadsign"),
        "scheduled_arrival": scheduled,
        "effective_arrival": effective,
        "delay_minutes": delay,
        "is_realtime": delay is not None or last_event is not None,
        "wheelchair_accessible": item.get("wheelchairAccessible"),
        "route_color": normalize_route_color(
            item.get("routeColor"),
            item.get("routeType"),
        ),
        "matricola_bus": item.get("matricolaBus"),
        "stale": False,
    }


def normalize_bikesharing(item: dict[str, Any]) -> dict[str, Any]:
    position = item.get("position") or [None, None]
    lat = item.get("lat", position[0] if len(position) > 0 else None)
    lon = item.get("lon", position[1] if len(position) > 1 else None)
    return {
        "id": str(item.get("id")),
        "name": item.get("name") or "",
        "address": item.get("address"),
        "lat": float(lat),
        "lon": float(lon),
        "bikes": int(item.get("bikes") or 0),
        "slots": int(item.get("slots") or 0),
        "total_slots": int(item.get("totalSlots") or 0),
    }