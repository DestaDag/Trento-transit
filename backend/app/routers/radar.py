from typing import Literal

from fastapi import APIRouter, Query, Request

from app.models.schemas import RadarResponse

router = APIRouter(prefix="/api/v1", tags=["radar"])


@router.get("/radar", response_model=RadarResponse)
async def get_radar(
    request: Request,
    lat: float = Query(default=46.0679, ge=-90.0, le=90.0),
    lon: float = Query(default=11.1211, ge=-180.0, le=180.0),
    radius_m: int = Query(default=5000, ge=100, le=25000),
    open_now: bool = Query(default=False),
    min_availability: Literal["Available", "Moderate", "Busy"] | None = Query(
        default=None
    ),
    accessible: bool = Query(default=False),
    amenities: str | None = Query(default=None),
) -> RadarResponse:
    service = request.app.state.radar_service
    amenity_list = (
        [item.strip() for item in amenities.split(",") if item.strip()]
        if amenities
        else None
    )
    return await service.compute_radar(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        open_now=open_now,
        min_availability=min_availability,
        accessible=accessible,
        amenities=amenity_list,
    )
