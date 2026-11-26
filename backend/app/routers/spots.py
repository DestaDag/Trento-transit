from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request

from app.models.schemas import CheckinRequest, CheckinResponse, StudySpotResponse
from app.services.occupancy import hash_client_id, is_open

router = APIRouter(prefix="/api/v1", tags=["spots"])


@router.get("/spots", response_model=list[StudySpotResponse])
async def list_spots(request: Request) -> list[StudySpotResponse]:
    service = request.app.state.radar_service
    return await service.list_spots()


@router.get("/spots/{spot_id}", response_model=StudySpotResponse)
async def get_spot(request: Request, spot_id: str) -> StudySpotResponse:
    service = request.app.state.radar_service
    spot = await service.get_spot_detail(spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Study spot not found")
    return spot


@router.post("/checkins", response_model=CheckinResponse)
async def create_checkin(
    request: Request,
    payload: CheckinRequest,
    x_client_id: str | None = Header(default=None, alias="X-Client-ID"),
) -> CheckinResponse:
    service = request.app.state.radar_service
    spot = await service.repo.get_study_spot(payload.spot_id)
    if spot is None:
        raise HTTPException(status_code=404, detail="Study spot not found")

    now = datetime.now(UTC)
    if not is_open(spot, now):
        raise HTTPException(
            status_code=400, detail="Cannot check in while the study spot is closed"
        )

    client_ip = request.client.host if request.client else None
    client_hash = hash_client_id(
        x_client_id, client_ip, service.settings.checkin_salt
    )
    window_start = now - timedelta(seconds=service.settings.checkin_rate_limit_seconds)
    if await service.repo.has_recent_checkin(payload.spot_id, client_hash, window_start):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: one check-in per spot every 15 minutes",
        )

    await service.repo.insert_occupancy_report(
        payload.spot_id, payload.level, client_hash
    )
    service.occupancy_cache.invalidate(payload.spot_id)
    updated_occ = await service.get_spot_occupancy(spot)
    return CheckinResponse(spot_id=payload.spot_id, occupancy=updated_occ, accepted=True)
