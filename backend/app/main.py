import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.adapters.trentino_trasporti import TrentinoTrasportiAdapter
from app.config import Settings
from app.db.repository import Repository
from app.routers import bikesharing, health, radar, spots, stops
from app.services.radar import RadarService


async def _periodic(interval_seconds: int, fn) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await fn()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo = Repository(cfg.database_path)
        await repo.initialize()
        await repo.seed_study_spots(cfg.study_spots_path)
        adapter = TrentinoTrasportiAdapter(
            base_url=cfg.tt_api_base_url,
            username=cfg.tt_api_username,
            password=cfg.tt_api_password,
            requested_with=cfg.tt_api_requested_with,
        )
        service = RadarService(cfg, repo, adapter)
        app.state.radar_service = service

        stops_count, _ = await repo.counts()
        if stops_count == 0:
            await service.sync_static_data()
            await service.sync_routes_data()
        await repo.compute_spot_stop_links()

        tasks: list[asyncio.Task[None]] = []
        if cfg.enable_scheduler:
            tasks.append(asyncio.create_task(_periodic(12 * 3600, service.sync_static_data)))
            tasks.append(asyncio.create_task(_periodic(15 * 60, service.sync_routes_data)))

        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="Trento Transit & Study Spot Radar",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(radar.router)
    app.include_router(stops.router)
    app.include_router(spots.router)
    app.include_router(bikesharing.router)
    return app


app = create_app()
