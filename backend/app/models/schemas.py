from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Stop(BaseModel):
    stop_id: str
    stop_code: str | None = None
    stop_name: str
    stop_lat: float
    stop_lon: float
    wheelchair_boarding: int = 0
    routes: list[dict[str, Any]] = Field(default_factory=list)


class RouteNews(BaseModel):
    header: str | None = None
    details: str | None = None
    url: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    route_id: str | None = None
    route_short_name: str | None = None


class Route(BaseModel):
    route_id: str
    short_name: str | None = None
    long_name: str | None = None
    area_id: str | None = None
    route_type: int | None = None
    route_color: str
    news: list[RouteNews] = Field(default_factory=list)


class StopTimeItem(BaseModel):
    stop_id: str
    stop_code: str | None = None
    stop_name: str | None = None
    stop_sequence: int = 0
    arrival_time: str | None = None
    departure_time: str | None = None


class Departure(BaseModel):
    trip_id: str
    route_id: str | None = None
    trip_headsign: str | None = None
    scheduled_arrival: datetime | None = None
    effective_arrival: datetime | None = None
    delay_minutes: int | None = None
    is_realtime: bool = False
    wheelchair_accessible: int | None = None
    route_color: str | None = None
    matricola_bus: str | None = None
    stale: bool = False


class TripDetail(Departure):
    stop_times: list[StopTimeItem] = Field(default_factory=list)


class ArrivalsResponse(BaseModel):
    stop_id: str
    stop_type: str
    departures: list[Departure] = Field(default_factory=list)
    alerts: list[RouteNews] = Field(default_factory=list)
    stale: bool = False
    updated_at: datetime


class BikeStation(BaseModel):
    id: str
    name: str
    address: str | None = None
    lat: float
    lon: float
    bikes: int = 0
    slots: int = 0
    total_slots: int = 0


class BikeSharingResponse(BaseModel):
    stations: list[BikeStation] = Field(default_factory=list)
    stale: bool = False
    updated_at: datetime


class OccupancyInfo(BaseModel):
    status: Literal["Available", "Moderate", "Busy", "Closed"]
    occupancy_percent: float | None = None
    source: Literal["live", "crowdsourced", "estimated"]


class LinkedStop(BaseModel):
    stop_id: str
    stop_code: str | None = None
    stop_name: str
    stop_type: str = "U"
    lat: float
    lon: float
    wheelchair_boarding: int = 0
    walk_distance_m: float
    walk_minutes: float
    routes: list[dict[str, Any]] = Field(default_factory=list)


class StudySpotResponse(BaseModel):
    spot_id: str
    name: str
    address: str | None = None
    lat: float
    lon: float
    hours: dict[str, Any] = Field(default_factory=dict)
    capacity_tier: str
    amenities: list[str] = Field(default_factory=list)
    occupancy: OccupancyInfo
    linked_stops: list[LinkedStop] = Field(default_factory=list)
    alerts: list[RouteNews] = Field(default_factory=list)


class CheckinRequest(BaseModel):
    spot_id: str
    level: int = Field(ge=1, le=3)


class CheckinResponse(BaseModel):
    spot_id: str
    occupancy: OccupancyInfo
    accepted: bool = True


class CommuteEstimate(BaseModel):
    mode: Literal["walk", "transit"]
    total_minutes: float
    walk_to_stop_minutes: float = 0.0
    wait_minutes: float = 0.0
    transit_minutes: float = 0.0
    walk_from_stop_minutes: float = 0.0
    origin_stop: LinkedStop | None = None
    destination_stop: LinkedStop | None = None
    next_departure: Departure | None = None


class RadarSpotItem(BaseModel):
    spot: StudySpotResponse
    distance_m: float
    commute: CommuteEstimate
    score: float


class RadarResponse(BaseModel):
    origin: dict[str, float]
    spots: list[RadarSpotItem] = Field(default_factory=list)
    nearby_stops: list[LinkedStop] = Field(default_factory=list)
    stale: bool = False
    updated_at: datetime


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "error"]
    stops_count: int
    spots_count: int
    upstream_configured: bool
    upstream_reachable: bool | None = None
