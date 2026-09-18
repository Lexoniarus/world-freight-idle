"""API v1 router composition."""

from fastapi import APIRouter, Depends

from app.api.v1 import (
    auth,
    contracts,
    dashboard,
    fleet,
    leaderboard,
    map,
    system,
    transports,
)
from app.api.v1.dependencies import require_same_origin


def build_v1_router() -> APIRouter:
    """Compose all version 1 resource routers."""
    router = APIRouter(
        prefix="/api/v1",
        dependencies=[Depends(require_same_origin)],
    )
    router.include_router(auth.router)
    router.include_router(leaderboard.router)
    router.include_router(map.router)
    router.include_router(dashboard.router)
    router.include_router(contracts.router)
    router.include_router(fleet.router)
    router.include_router(transports.router)
    router.include_router(system.router)
    return router
