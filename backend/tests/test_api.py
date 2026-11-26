from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def _make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        tt_api_base_url="https://mock.tndigit.local/gtlservice",
        tt_api_username="u",
        tt_api_password="p",
        database_path=str(tmp_path / "test.db"),
        enable_scheduler=False,
    )
    app = create_app(settings)
    return TestClient(app)


def test_health_and_spots_seeded(tmp_path: Path) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://mock.tndigit.local/gtlservice/stops").respond(200, json=[])
        router.get("https://mock.tndigit.local/gtlservice/routes").respond(200, json=[])
        with _make_client(tmp_path) as client:
            health = client.get("/api/v1/health")
            assert health.status_code == 200
            body = health.json()
            assert body["status"] == "ok"
            assert body["database"] == "ok"
            assert body["spots_count"] >= 10

            spots = client.get("/api/v1/spots")
            assert spots.status_code == 200
            assert len(spots.json()) >= 10

            missing = client.get("/api/v1/spots/does-not-exist")
            assert missing.status_code == 404


def test_checkin_rate_limit_and_closed_guard(tmp_path: Path, monkeypatch) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://mock.tndigit.local/gtlservice/stops").respond(200, json=[])
        router.get("https://mock.tndigit.local/gtlservice/routes").respond(200, json=[])
        with _make_client(tmp_path) as client:
            monkeypatch.setattr("app.routers.spots.is_open", lambda *_args, **_kw: False)
            closed_res = client.post(
                "/api/v1/checkins",
                json={"spot_id": "buc", "level": 1},
                headers={"X-Client-ID": "client-1"},
            )
            assert closed_res.status_code == 400

            monkeypatch.setattr("app.routers.spots.is_open", lambda *_args, **_kw: True)
            monkeypatch.setattr("app.services.occupancy.is_open", lambda *_args, **_kw: True)
            ok_res = client.post(
                "/api/v1/checkins",
                json={"spot_id": "buc", "level": 1},
                headers={"X-Client-ID": "client-1"},
            )
            assert ok_res.status_code == 200
            occ = ok_res.json()["occupancy"]
            assert occ["source"] == "crowdsourced"
            assert occ["status"] == "Available"

            dup_res = client.post(
                "/api/v1/checkins",
                json={"spot_id": "buc", "level": 3},
                headers={"X-Client-ID": "client-1"},
            )
            assert dup_res.status_code == 429


def test_arrivals_stale_fallback_and_trip_detail(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    trips_payload = [
        {
            "tripId": f"t-{i}",
            "routeId": "5",
            "tripHeadsign": "Povo",
            "delay": 2,
            "lastEventRecivedAt": now.isoformat(),
            "oraArrivoProgrammataAFermataSelezionata": (
                now + timedelta(minutes=3 + i * 5)
            ).isoformat().replace("+00:00", "Z"),
            "oraArrivoEffettivaAFermataSelezionata": (
                now + timedelta(minutes=5 + i * 5)
            ).isoformat().replace("+00:00", "Z"),
            "wheelchairAccessible": 1,
            "routeType": 3,
        }
        for i in range(4)
    ]
    trip_detail_payload = {
        **trips_payload[0],
        "stopTimes": [
            {
                "stopId": "2001",
                "stopCode": "2001",
                "stopName": "Piazza Dante",
                "stopSequence": 1,
                "arrivalTime": "10:00:00",
                "departureTime": "10:01:00",
            },
            {
                "stopId": "2002",
                "stopCode": "2002",
                "stopName": "Povo Polo",
                "stopSequence": 2,
                "arrivalTime": "10:15:00",
                "departureTime": "10:15:00",
            },
        ],
    }

    with respx.mock(assert_all_called=False) as router:
        router.get("https://mock.tndigit.local/gtlservice/stops").respond(200, json=[])
        router.get("https://mock.tndigit.local/gtlservice/routes").respond(200, json=[])
        trips_route = router.get("https://mock.tndigit.local/gtlservice/trips_new").respond(
            200, json=trips_payload
        )
        router.get("https://mock.tndigit.local/gtlservice/trips/t-0").respond(
            200, json=trip_detail_payload
        )

        with _make_client(tmp_path) as client:
            res = client.get("/api/v1/stops/2001/arrivals?type=U&limit=2")
            assert res.status_code == 200
            data = res.json()
            assert data["stale"] is False
            assert len(data["departures"]) == 2

            # Invalidate TTL cache and simulate upstream 503 -> should serve stale cache
            client.app.state.radar_service.trips_cache.invalidate(("2001", "U", 2))
            trips_route.mock(
                return_value=httpx.Response(503, json={"error": "upstream down"})
            )
            stale_res = client.get("/api/v1/stops/2001/arrivals?type=U&limit=2")
            assert stale_res.status_code == 200
            stale_data = stale_res.json()
            assert stale_data["stale"] is True
            assert len(stale_data["departures"]) == 2

            detail_res = client.get("/api/v1/trips/t-0")
            assert detail_res.status_code == 200
            assert len(detail_res.json()["stop_times"]) == 2


def test_bikesharing_and_radar_filtering(tmp_path: Path) -> None:
    stops_payload = [
        {
            "stopId": "2001",
            "stopCode": "2001",
            "stopName": "Piazza Duomo",
            "stopLat": 46.0679,
            "stopLon": 11.1211,
            "wheelchairBoarding": 1,
            "routes": [{"routeId": "5", "routeShortName": "5"}],
        },
        {
            "stopId": "2002",
            "stopCode": "2002",
            "stopName": "Povo Sommarive",
            "stopLat": 46.0671,
            "stopLon": 11.1507,
            "wheelchairBoarding": 1,
            "routes": [{"routeId": "5", "routeShortName": "5"}],
        },
    ]
    bikesharing_payload = [
        {
            "id": "b1",
            "name": "Piazza Duomo",
            "address": "Piazza Duomo",
            "position": [46.0675, 11.1215],
            "bikes": 7,
            "slots": 5,
            "totalSlots": 12,
        }
    ]
    with respx.mock(assert_all_called=False) as router:
        router.get(
            "https://mock.tndigit.local/gtlservice/stops", params={"type": "U"}
        ).respond(200, json=stops_payload)
        router.get(
            "https://mock.tndigit.local/gtlservice/stops", params={"type": "E"}
        ).respond(200, json=[])
        router.get("https://mock.tndigit.local/gtlservice/routes").respond(200, json=[])
        router.get("https://mock.tndigit.local/gtlservice/trips_new").respond(
            200, json=[]
        )
        router.get("https://mock.tndigit.local/gtlservice/poi/bikesharing").respond(
            200, json=bikesharing_payload
        )

        with _make_client(tmp_path) as client:
            bike_res = client.get("/api/v1/bikesharing")
            assert bike_res.status_code == 200
            stations = bike_res.json()["stations"]
            assert stations[0]["lat"] == 46.0675
            assert stations[0]["lon"] == 11.1215

            radar_res = client.get(
                "/api/v1/radar?lat=46.0679&lon=11.1211&accessible=true&amenities=quiet_zone"
            )
            assert radar_res.status_code == 200
            radar_data = radar_res.json()
            assert len(radar_data["nearby_stops"]) >= 1
            assert len(radar_data["spots"]) >= 1
            for item in radar_data["spots"]:
                amenities = item["spot"]["amenities"]
                assert "accessible" in amenities
                assert "quiet_zone" in amenities
