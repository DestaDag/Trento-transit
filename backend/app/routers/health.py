import aiosqlite
from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    service = request.app.state.radar_service
    try:
        stops_count, spots_count = await service.repo.counts()
        db_status = "ok"
    except (aiosqlite.Error, OSError):
        stops_count, spots_count = 0, 0
        db_status = "error"

    upstream_configured = bool(
        service.settings.tt_api_username and service.settings.tt_api_password
    )
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        stops_count=stops_count,
        spots_count=spots_count,
        upstream_configured=upstream_configured,
    )
