from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.models.schemas import ArrivalsResponse, TripDetail

router = APIRouter(prefix="/api/v1", tags=["stops"])


@router.get("/stops/{stop_id}/arrivals", response_model=ArrivalsResponse)
async def get_stop_arrivals(
    request: Request,
    stop_id: str,
    type: Literal["U", "E"] = Query(default="U"),
    limit: int = Query(default=5, ge=1, le=20),
) -> ArrivalsResponse:
    service = request.app.state.radar_service
    try:
        return await service.get_stop_arrivals(stop_id=stop_id, stop_type=type, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Upstream transit arrivals unavailable"
        ) from exc


@router.get("/trips/{trip_id}", response_model=TripDetail)
async def get_trip_detail(request: Request, trip_id: str) -> TripDetail:
    service = request.app.state.radar_service
    try:
        return await service.get_trip_detail(trip_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Upstream trip detail unavailable"
        ) from exc
