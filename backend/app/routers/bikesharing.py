from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import BikeSharingResponse

router = APIRouter(prefix="/api/v1", tags=["bikesharing"])


@router.get("/bikesharing", response_model=BikeSharingResponse)
async def get_bikesharing(request: Request) -> BikeSharingResponse:
    service = request.app.state.radar_service
    try:
        return await service.get_bikesharing()
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="Bike-sharing feed unavailable"
        ) from exc
