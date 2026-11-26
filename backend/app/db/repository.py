import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite


class Repository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).with_name("schema.sql")
        async with aiosqlite.connect(self.database_path) as db:
            await db.executescript(schema_path.read_text(encoding="utf-8"))
            await db.commit()

    async def upsert_stops(self, stops: list[dict[str, Any]]) -> None:
        if not stops:
            return
        updated = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.database_path) as db:
            for stop in stops:
                stop_id = str(stop["stop_id"])
                await db.execute(
                    """
                    INSERT INTO transit_stops
                    (stop_id, stop_code, stop_name, stop_type, lat, lon,
                     wheelchair_boarding, routes_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stop_id) DO UPDATE SET
                      stop_code=excluded.stop_code,
                      stop_name=excluded.stop_name,
                      stop_type=excluded.stop_type,
                      lat=excluded.lat,
                      lon=excluded.lon,
                      wheelchair_boarding=excluded.wheelchair_boarding,
                      routes_json=excluded.routes_json,
                      updated_at=excluded.updated_at
                    """,
                    (
                        stop_id,
                        stop.get("stop_code"),
                        stop["stop_name"],
                        stop.get("stop_type", "U"),
                        stop["stop_lat"],
                        stop["stop_lon"],
                        stop.get("wheelchair_boarding", 0),
                        json.dumps(stop.get("routes", [])),
                        updated,
                    ),
                )
                await db.execute(
                    "DELETE FROM transit_stops_rtree WHERE id = ?", (stop_id,)
                )
                lat, lon = stop["stop_lat"], stop["stop_lon"]
                await db.execute(
                    "INSERT INTO transit_stops_rtree "
                    "(id, min_lat, max_lat, min_lon, max_lon) VALUES (?, ?, ?, ?, ?)",
                    (stop_id, lat, lat, lon, lon),
                )
            await db.commit()

    async def upsert_routes(self, routes: list[dict[str, Any]]) -> None:
        if not routes:
            return
        updated = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.database_path) as db:
            for route in routes:
                await db.execute(
                    """
                    INSERT INTO transit_routes
                    (route_id, area_id, short_name, long_name, route_type,
                     color_hex, news_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(route_id) DO UPDATE SET
                      area_id=excluded.area_id,
                      short_name=excluded.short_name,
                      long_name=excluded.long_name,
                      route_type=excluded.route_type,
                      color_hex=excluded.color_hex,
                      news_json=excluded.news_json,
                      updated_at=excluded.updated_at
                    """,
                    (
                        route["route_id"],
                        route.get("area_id"),
                        route.get("short_name"),
                        route.get("long_name"),
                        route.get("route_type"),
                        route["route_color"],
                        json.dumps(route.get("news", []), default=str),
                        updated,
                    ),
                )
            await db.commit()

    async def seed_study_spots(self, json_path: str) -> int:
        spots = json.loads(Path(json_path).read_text(encoding="utf-8"))
        async with aiosqlite.connect(self.database_path) as db:
            for spot in spots:
                await db.execute(
                    """
                    INSERT INTO study_spots
                    (spot_id, name, address, lat, lon, hours_json,
                     holidays_json, capacity_tier, amenities_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(spot_id) DO UPDATE SET
                      name=excluded.name, address=excluded.address,
                      lat=excluded.lat, lon=excluded.lon,
                      hours_json=excluded.hours_json,
                      holidays_json=excluded.holidays_json,
                      capacity_tier=excluded.capacity_tier,
                      amenities_json=excluded.amenities_json
                    """,
                    (
                        spot["spot_id"],
                        spot["name"],
                        spot.get("address"),
                        spot["lat"],
                        spot["lon"],
                        json.dumps(spot.get("hours", {})),
                        json.dumps(spot.get("holiday_overrides", {})),
                        spot.get("capacity_tier", "medium"),
                        json.dumps(spot.get("amenities", [])),
                    ),
                )
            await db.commit()
        return len(spots)

    async def compute_spot_stop_links(self, radius_m: float = 500.0) -> int:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            spots = await db.execute_fetchall(
                "SELECT spot_id, lat, lon FROM study_spots"
            )
            stops = await db.execute_fetchall(
                "SELECT stop_id, lat, lon FROM transit_stops"
            )
            count = 0
            for spot in spots:
                for stop in stops:
                    distance = haversine(
                        spot["lat"], spot["lon"], stop["lat"], stop["lon"]
                    )
                    if distance <= radius_m:
                        minutes = distance / (4.8 * 1000 / 60)
                        await db.execute(
                            """
                            INSERT INTO spot_stop_links
                            (spot_id, stop_id, walk_distance_m, walk_minutes)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(spot_id, stop_id) DO UPDATE SET
                              walk_distance_m=excluded.walk_distance_m,
                              walk_minutes=excluded.walk_minutes
                            """,
                            (spot["spot_id"], stop["stop_id"], distance, minutes),
                        )
                        count += 1
            await db.commit()
        return count

    async def list_study_spots(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall("SELECT * FROM study_spots")
            return [dict(row) for row in rows]

    async def insert_occupancy_report(
        self, spot_id: str, level: int, client_hash: str
    ) -> None:
        now = datetime.now(UTC)
        cutoff = (now.timestamp() - 86400)
        async with aiosqlite.connect(self.database_path) as db:
            await db.execute(
                """
                INSERT INTO occupancy_reports (spot_id, level, client_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    spot_id,
                    level,
                    client_hash,
                    now.isoformat(),
                ),
            )
            await db.execute(
                "DELETE FROM occupancy_reports WHERE created_at < ?",
                (datetime.fromtimestamp(cutoff, UTC).isoformat(),),
            )
            await db.commit()

    async def recent_occupancy_reports(
        self, spot_id: str, now: datetime | None = None
    ) -> list[tuple[int, datetime]]:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = None
            cutoff = (
                (now or datetime.now(UTC)).timestamp() - 86400
            )
            rows = await db.execute_fetchall(
                """
                SELECT level, created_at FROM occupancy_reports
                WHERE spot_id = ? AND created_at >= ?
                """,
                (spot_id, datetime.fromtimestamp(cutoff, UTC).isoformat()),
            )
        results = []
        for level, created_at in rows:
            try:
                timestamp = datetime.fromisoformat(created_at)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
            except (TypeError, ValueError):
                continue
            results.append((int(level), timestamp))
        return results

    async def has_recent_checkin(
        self, spot_id: str, client_hash: str, since: datetime
    ) -> bool:
        async with aiosqlite.connect(self.database_path) as db:
            rows = await db.execute_fetchall(
                """
                SELECT 1 FROM occupancy_reports
                WHERE spot_id = ? AND client_hash = ? AND created_at >= ?
                LIMIT 1
                """,
                (spot_id, client_hash, since.isoformat()),
            )
            return len(rows) > 0

    async def get_study_spot(self, spot_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM study_spots WHERE spot_id = ?", (spot_id,)
            )
            return dict(rows[0]) if rows else None

    async def get_spot_stop_links(
        self, spot_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = """
            SELECT l.spot_id, l.walk_distance_m, l.walk_minutes,
                   s.stop_id, s.stop_code, s.stop_name, s.stop_type,
                   s.lat, s.lon, s.wheelchair_boarding, s.routes_json
            FROM spot_stop_links l
            JOIN transit_stops s ON s.stop_id = l.stop_id
        """
        params: tuple[Any, ...] = ()
        if spot_id is not None:
            query += " WHERE l.spot_id = ?"
            params = (spot_id,)
        query += " ORDER BY l.walk_distance_m ASC"
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(query, params)
            return [dict(row) for row in rows]

    async def find_stops_near(
        self,
        lat: float,
        lon: float,
        radius_m: float = 800.0,
        accessible_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        lat_delta = radius_m / 111_320.0
        cos_lat = max(0.2, math.cos(math.radians(lat)))
        lon_delta = radius_m / (111_320.0 * cos_lat)
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                """
                SELECT s.*
                FROM transit_stops s
                JOIN transit_stops_rtree r ON r.id = s.stop_id
                WHERE r.min_lat >= ? AND r.max_lat <= ?
                  AND r.min_lon >= ? AND r.max_lon <= ?
                """,
                (
                    lat - lat_delta,
                    lat + lat_delta,
                    lon - lon_delta,
                    lon + lon_delta,
                ),
            )
        candidates: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            if accessible_only and int(item.get("wheelchair_boarding") or 0) <= 0:
                continue
            dist = haversine(lat, lon, item["lat"], item["lon"])
            if dist <= radius_m:
                item["walk_distance_m"] = round(dist, 1)
                item["walk_minutes"] = round(dist / (4.8 * 1000 / 60), 1)
                candidates.append(item)
        candidates.sort(key=lambda s: s["walk_distance_m"])
        return candidates[:limit]

    async def get_stop(self, stop_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM transit_stops WHERE stop_id = ?", (stop_id,)
            )
            return dict(rows[0]) if rows else None

    async def list_routes(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.database_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall("SELECT * FROM transit_routes")
            return [dict(row) for row in rows]

    async def counts(self) -> tuple[int, int]:
        async with aiosqlite.connect(self.database_path) as db:
            stops_row = await db.execute_fetchall("SELECT COUNT(*) FROM transit_stops")
            spots_row = await db.execute_fetchall("SELECT COUNT(*) FROM study_spots")
            return int(stops_row[0][0]), int(spots_row[0][0])


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