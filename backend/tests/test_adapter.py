from datetime import UTC, datetime

import httpx
import respx

from app.adapters.trentino_trasporti import (
    TrentinoTrasportiAdapter,
    normalize_bikesharing,
    normalize_route,
    normalize_route_color,
    normalize_trip,
    parse_dotnet_date,
)

BASE = "https://app-tpl.tndigit.it/gtlservice"


@respx.mock
async def test_trips_double_limit_sorted_and_sliced():
    route = respx.get(f"{BASE}/trips_new").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "tripId": "later",
                    "routeId": "5",
                    "oraArrivoProgrammataAFermataSelezionata": "2099-01-01T12:00:00Z",
                    "oraArrivoEffettivaAFermataSelezionata": "2099-01-01T12:05:00Z",
                    "delay": 5,
                    "lastEventRecivedAt": None,
                },
                {
                    "tripId": "earlier",
                    "routeId": "5",
                    "oraArrivoProgrammataAFermataSelezionata": "2099-01-01T11:50:00Z",
                    "oraArrivoEffettivaAFermataSelezionata": "2099-01-01T11:55:00Z",
                    "delay": None,
                    "lastEventRecivedAt": "2099-01-01T11:54:00Z",
                },
            ],
        )
    )
    async with httpx.AsyncClient() as client:
        adapter = TrentinoTrasportiAdapter(BASE, "user", "pass", client=client)
        trips = await adapter.get_trips_new("100", "U", 1)

    assert route.called
    assert len(trips) == 1
    assert trips[0]["trip_id"] == "earlier"
    assert trips[0]["is_realtime"] is True
    assert trips[0]["effective_arrival"].tzinfo is not None


def test_nullable_route_color_and_dotnet_alert():
    assert normalize_route_color(None, 2) == "#7B1FA2"
    assert normalize_route_color("abcdef", 3) == "#ABCDEF"
    start = parse_dotnet_date("/Date(1673654400)/")
    assert start == datetime(2023, 1, 14, 0, 0, tzinfo=UTC)

    route = normalize_route(
        {
            "routeId": "5",
            "routeType": 3,
            "routeColor": None,
            "news": [
                {
                    "header": "Works",
                    "startDate": "/Date(0)/",
                    "endDate": "/Date(4102444800000)/",
                }
            ],
        }
    )
    assert route["route_color"] == "#1976D2"
    assert route["news"][0]["header"] == "Works"


def test_nullable_realtime_and_bikesharing_position():
    trip = normalize_trip(
        {
            "tripId": "10",
            "delay": None,
            "lastEventRecivedAt": None,
            "matricolaBus": None,
        }
    )
    assert trip["is_realtime"] is False

    bike = normalize_bikesharing(
        {"id": "1", "name": "Dante", "position": [46.067, 11.121], "bikes": 3, "slots": 7}
    )
    assert bike["lat"] == 46.067
    assert bike["lon"] == 11.121