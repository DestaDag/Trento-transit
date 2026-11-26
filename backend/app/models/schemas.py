from datetime import datetime
from typing import Any

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


class Route(BaseModel):
    route_id: str
    short_name: str | None = None
    long_name: str | None = None
    area_id: str | None = None
    route_type: int | None = None
    route_color: str
    news: list[RouteNews] = Field(default_factory=list)


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


class BikeStation(BaseModel):
    id: str
    name: str
    address: str | None = None
    lat: float
    lon: float
    bikes: int = 0
    slots: int = 0
    total_slots: int = 0