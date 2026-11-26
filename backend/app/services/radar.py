import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiosqlite
import httpx

from app.adapters.trentino_trasporti import TrentinoTrasportiAdapter
from app.config import Settings
from app.db.repository import Repository
from app.models.schemas import (
    ArrivalsResponse,
    BikeSharingResponse,
    BikeStation,
    CommuteEstimate,
    Departure,
    LinkedStop,
    OccupancyInfo,
    RadarResponse,
    RadarSpotItem,
    RouteNews,
    StudySpotResponse,
    TripDetail,
)
from app.services.cache import SingleFlightCache
from app.services.occupancy import haversine, resolve_occupancy

logger = logging.getLogger(__name__)

_AVAILABILITY_ORDER = {"Available": 0, "Moderate": 1, "Busy": 2, "Closed": 3}
_AVAILABILITY_PENALTY = {"Available": 0.0, "Moderate": 8.0, "Busy": 20.0, "Closed": 1000.0}


class RadarService:
    def __init__(self, settings: Settings, repo: Repository, adapter: TrentinoTrasportiAdapter) -> None:
        self.settings = settings
        self.repo = repo
        self.adapter = adapter
        self.trips_cache: SingleFlightCache[list[dict[str, Any]]] = SingleFlightCache(
            ttl_seconds=float(settings.tt_trips_cache_ttl_seconds)
        )
        self.trip_detail_cache: SingleFlightCache[dict[str, Any]] = SingleFlightCache(
            ttl_seconds=float(settings.tt_trips_cache_ttl_seconds)
        )
        self.bikesharing_cache: SingleFlightCache[list[dict[str, Any]]] = SingleFlightCache(
            ttl_seconds=60.0
        )
        self.occupancy_cache: SingleFlightCache[dict[str, Any]] = SingleFlightCache(
            ttl_seconds=30.0
        )
        self._stale_trips: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
        self._stale_trip_detail: dict[str, dict[str, Any]] = {}
        self._stale_bikesharing: list[dict[str, Any]] | None = None

    async def sync_static_data(self) -> None:
        if not (self.settings.tt_api_username and self.settings.tt_api_password):
            return
        try:
            urban = await self.adapter.get_stops("U")
            extra = await self.adapter.get_stops("E")
            all_stops = [{**s, "stop_type": "U"} for s in urban] + [
                {**s, "stop_type": "E"} for s in extra
            ]
            if all_stops:
                await self.repo.upsert_stops(all_stops)
                await self.repo.compute_spot_stop_links()
        except (httpx.HTTPError, TimeoutError, ValueError, aiosqlite.Error) as exc:
            logger.warning("Upstream stops sync failed: %s", type(exc).__name__)

    async def sync_routes_data(self) -> None:
        if not (self.settings.tt_api_username and self.settings.tt_api_password):
            return
        try:
            routes = await self.adapter.get_routes(self.settings.tt_trento_areas)
            if routes:
                await self.repo.upsert_routes(routes)
        except (httpx.HTTPError, TimeoutError, ValueError, aiosqlite.Error) as exc:
            logger.warning("Upstream routes sync failed: %s", type(exc).__name__)

    async def _alerts_by_route(self) -> dict[str, list[RouteNews]]:
        routes = await self.repo.list_routes()
        now = datetime.now(UTC)
        by_route: dict[str, list[RouteNews]] = {}
        for route in routes:
            try:
                news_list = json.loads(route.get("news_json") or "[]")
            except (TypeError, ValueError):
                news_list = []
            active: list[RouteNews] = []
            for item in news_list:
                start = _parse_dt(item.get("start_date"))
                end = _parse_dt(item.get("end_date"))
                if (start is None or start <= now) and (end is None or end >= now):
                    active.append(
                        RouteNews(
                            header=item.get("header"),
                            details=item.get("details"),
                            url=item.get("url"),
                            start_date=start,
                            end_date=end,
                            route_id=str(route["route_id"]),
                            route_short_name=route.get("short_name"),
                        )
                    )
            if active:
                by_route[str(route["route_id"])] = active
        return by_route

    async def get_stop_arrivals(
        self, stop_id: str, stop_type: str = "U", limit: int = 5
    ) -> ArrivalsResponse:
        key = (stop_id, stop_type, limit)
        stale_used = False

        async def _fetch() -> list[dict[str, Any]]:
            ref_dt = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            data = await self.adapter.get_trips_new(
                stop_id=stop_id, stop_type=stop_type, limit=limit, ref_date_time=ref_dt
            )
            self._stale_trips[key] = data
            return data

        def _fallback() -> list[dict[str, Any]] | None:
            nonlocal stale_used
            if not self.settings.cache_stale_fallback:
                return None
            cached = self._stale_trips.get(key)
            if cached is not None:
                stale_used = True
                return [{**item, "stale": True} for item in cached]
            return None

        raw_departures = await self.trips_cache.get_or_fetch(
            key, _fetch, stale_fallback=_fallback
        )
        alerts_by_route = await self._alerts_by_route()
        stop_row = await self.repo.get_stop(stop_id)
        alerts: list[RouteNews] = []
        if stop_row:
            for r in _parse_json_list(stop_row.get("routes_json")):
                rid = str(r.get("routeId") or r.get("route_id") or "")
                alerts.extend(alerts_by_route.get(rid, []))

        departures = [Departure(**item) for item in raw_departures]
        for dep in departures:
            if dep.route_id and dep.route_id in alerts_by_route:
                for alert in alerts_by_route[dep.route_id]:
                    if alert not in alerts:
                        alerts.append(alert)

        return ArrivalsResponse(
            stop_id=stop_id,
            stop_type=stop_type,
            departures=departures,
            alerts=alerts,
            stale=stale_used or any(d.stale for d in departures),
            updated_at=datetime.now(UTC),
        )

    async def get_trip_detail(self, trip_id: str) -> TripDetail:
        stale_used = False

        async def _fetch() -> dict[str, Any]:
            data = await self.adapter.get_trip(trip_id)
            self._stale_trip_detail[trip_id] = data
            return data

        def _fallback() -> dict[str, Any] | None:
            nonlocal stale_used
            if not self.settings.cache_stale_fallback:
                return None
            cached = self._stale_trip_detail.get(trip_id)
            if cached is not None:
                stale_used = True
                return {**cached, "stale": True}
            return None

        raw = await self.trip_detail_cache.get_or_fetch(
            trip_id, _fetch, stale_fallback=_fallback
        )
        return TripDetail(**{**raw, "stale": stale_used or raw.get("stale", False)})

    async def get_bikesharing(self) -> BikeSharingResponse:
        stale_used = False

        async def _fetch() -> list[dict[str, Any]]:
            data = await self.adapter.get_bikesharing()
            self._stale_bikesharing = data
            return data

        def _fallback() -> list[dict[str, Any]] | None:
            nonlocal stale_used
            if not self.settings.cache_stale_fallback:
                return None
            if self._stale_bikesharing is not None:
                stale_used = True
                return self._stale_bikesharing
            return None

        raw = await self.bikesharing_cache.get_or_fetch(
            "bikesharing", _fetch, stale_fallback=_fallback
        )
        return BikeSharingResponse(
            stations=[BikeStation(**s) for s in raw],
            stale=stale_used,
            updated_at=datetime.now(UTC),
        )

    async def get_spot_occupancy(self, spot: dict[str, Any]) -> OccupancyInfo:
        spot_id = spot["spot_id"]

        async def _compute() -> dict[str, Any]:
            reports = await self.repo.recent_occupancy_reports(spot_id)
            return resolve_occupancy(spot, reports)

        result = await self.occupancy_cache.get_or_fetch(spot_id, _compute)
        return OccupancyInfo(**result)

    async def list_spots(self) -> list[StudySpotResponse]:
        spots = await self.repo.list_study_spots()
        links = await self.repo.get_spot_stop_links()
        alerts_by_route = await self._alerts_by_route()
        links_by_spot: dict[str, list[dict[str, Any]]] = {}
        for link in links:
            links_by_spot.setdefault(link["spot_id"], []).append(link)

        results: list[StudySpotResponse] = []
        for spot in spots:
            occ = await self.get_spot_occupancy(spot)
            results.append(
                _build_spot_response(
                    spot, occ, links_by_spot.get(spot["spot_id"], []), alerts_by_route
                )
            )
        return results

    async def get_spot_detail(self, spot_id: str) -> StudySpotResponse | None:
        spot = await self.repo.get_study_spot(spot_id)
        if not spot:
            return None
        links = await self.repo.get_spot_stop_links(spot_id)
        alerts_by_route = await self._alerts_by_route()
        occ = await self.get_spot_occupancy(spot)
        return _build_spot_response(spot, occ, links, alerts_by_route)

    async def compute_radar(
        self,
        lat: float,
        lon: float,
        radius_m: int = 5000,
        open_now: bool = False,
        min_availability: str | None = None,
        accessible: bool = False,
        amenities: list[str] | None = None,
    ) -> RadarResponse:
        nearby_raw = await self.repo.find_stops_near(
            lat, lon, radius_m=min(float(radius_m), 800.0), accessible_only=accessible, limit=12
        )
        nearby_stops = [_to_linked_stop(s) for s in nearby_raw]

        any_stale = False
        origin_departures: dict[str, list[Departure]] = {}
        for stop in nearby_stops[:3]:
            try:
                arrivals = await self.get_stop_arrivals(stop.stop_id, stop.stop_type, limit=3)
                origin_departures[stop.stop_id] = arrivals.departures
                if arrivals.stale:
                    any_stale = True
            except (httpx.HTTPError, TimeoutError, ValueError):
                origin_departures[stop.stop_id] = []

        all_spots = await self.list_spots()
        required_amenities = {a.strip().lower() for a in (amenities or []) if a.strip()}
        if accessible:
            required_amenities.add("accessible")

        max_avail_rank = _AVAILABILITY_ORDER.get(min_availability or "", 3)
        now = datetime.now(UTC)

        ranked: list[RadarSpotItem] = []
        for spot in all_spots:
            spot_amenities = {a.lower() for a in spot.amenities}
            if required_amenities and not required_amenities.issubset(spot_amenities):
                continue
            if open_now and spot.occupancy.status == "Closed":
                continue
            if min_availability and _AVAILABILITY_ORDER[spot.occupancy.status] > max_avail_rank:
                continue

            dist_m = haversine(lat, lon, spot.lat, spot.lon)
            if dist_m > radius_m:
                continue

            commute = _estimate_commute(
                dist_m, nearby_stops, spot.linked_stops, origin_departures, accessible, now
            )
            penalty = _AVAILABILITY_PENALTY.get(spot.occupancy.status, 100.0)
            score = round(commute.total_minutes + penalty, 2)
            ranked.append(
                RadarSpotItem(
                    spot=spot,
                    distance_m=round(dist_m, 1),
                    commute=commute,
                    score=score,
                )
            )

        ranked.sort(key=lambda item: item.score)
        return RadarResponse(
            origin={"lat": lat, "lon": lon},
            spots=ranked,
            nearby_stops=nearby_stops,
            stale=any_stale,
            updated_at=now,
        )


def _estimate_commute(
    direct_dist_m: float,
    origin_stops: list[LinkedStop],
    dest_stops: list[LinkedStop],
    origin_departures: dict[str, list[Departure]],
    accessible: bool,
    now: datetime,
) -> CommuteEstimate:
    walk_only_min = round(direct_dist_m / (4.8 * 1000 / 60), 1)
    best = CommuteEstimate(mode="walk", total_minutes=walk_only_min)

    if direct_dist_m <= 550 or not origin_stops or not dest_stops:
        return best

    eligible_dest = [
        s for s in dest_stops if not accessible or s.wheelchair_boarding > 0
    ]
    if not eligible_dest:
        return best
    dest_stop = eligible_dest[0]

    for o_stop in origin_stops[:3]:
        deps = origin_departures.get(o_stop.stop_id, [])
        if accessible:
            deps = [d for d in deps if d.wheelchair_accessible in (None, 1)]
        next_dep = deps[0] if deps else None
        wait_min = 6.0
        if next_dep and (next_dep.effective_arrival or next_dep.scheduled_arrival):
            target = next_dep.effective_arrival or next_dep.scheduled_arrival
            assert target is not None
            wait_min = max(1.0, round((target - now).total_seconds() / 60, 1))

        ride_dist = haversine(o_stop.lat, o_stop.lon, dest_stop.lat, dest_stop.lon)
        transit_min = max(2.0, round(ride_dist / (20.0 * 1000 / 60), 1))
        total = round(o_stop.walk_minutes + wait_min + transit_min + dest_stop.walk_minutes, 1)
        if total < best.total_minutes:
            best = CommuteEstimate(
                mode="transit",
                total_minutes=total,
                walk_to_stop_minutes=o_stop.walk_minutes,
                wait_minutes=wait_min,
                transit_minutes=transit_min,
                walk_from_stop_minutes=dest_stop.walk_minutes,
                origin_stop=o_stop,
                destination_stop=dest_stop,
                next_departure=next_dep,
            )
    return best


def _build_spot_response(
    spot: dict[str, Any],
    occupancy: OccupancyInfo,
    links: list[dict[str, Any]],
    alerts_by_route: dict[str, list[RouteNews]],
) -> StudySpotResponse:
    linked_stops = [_to_linked_stop(link) for link in links]
    seen_headers: set[str] = set()
    alerts: list[RouteNews] = []
    for stop in linked_stops:
        for route in stop.routes:
            rid = str(route.get("routeId") or route.get("route_id") or "")
            for alert in alerts_by_route.get(rid, []):
                key = f"{alert.route_id}:{alert.header}"
                if key not in seen_headers:
                    seen_headers.add(key)
                    alerts.append(alert)
    return StudySpotResponse(
        spot_id=spot["spot_id"],
        name=spot["name"],
        address=spot.get("address"),
        lat=spot["lat"],
        lon=spot["lon"],
        hours=_parse_json_dict(spot.get("hours_json")),
        capacity_tier=spot["capacity_tier"],
        amenities=_parse_json_list(spot.get("amenities_json")),
        occupancy=occupancy,
        linked_stops=linked_stops,
        alerts=alerts,
    )


def _to_linked_stop(row: dict[str, Any]) -> LinkedStop:
    return LinkedStop(
        stop_id=str(row["stop_id"]),
        stop_code=row.get("stop_code"),
        stop_name=row["stop_name"],
        stop_type=row.get("stop_type", "U"),
        lat=row["lat"],
        lon=row["lon"],
        wheelchair_boarding=int(row.get("wheelchair_boarding") or 0),
        walk_distance_m=round(float(row.get("walk_distance_m") or 0.0), 1),
        walk_minutes=round(float(row.get("walk_minutes") or 0.0), 1),
        routes=_parse_json_list(row.get("routes_json")),
    )


def _parse_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except ValueError:
            return []
    return []


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None
