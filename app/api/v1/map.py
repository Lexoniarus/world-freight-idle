"""Authenticated location projection for the map-first interface."""

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_map_service
from app.services.map_locations import MapLocationService

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/hubs")
async def list_map_hubs(
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Resolve public freight hubs with the existing cached provider."""
    return {"hubs": await service.list_hubs()}
