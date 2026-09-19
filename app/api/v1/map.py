"""Authenticated location projection for the map-first interface."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import (
    get_current_user,
    get_map_service,
    get_multiplayer_map_service,
)
from app.domain.world import FacilityQuery
from app.services.map_locations import MapLocationService
from app.services.multiplayer_map import MultiplayerMapService

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/hubs")
async def list_map_hubs(
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Project verified public facilities without external lookups."""
    return {"hubs": await service.list_hubs()}


@router.get("/facilities")
def list_map_facilities(
    bbox: str | None = None,
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Query verified public facilities by optional WGS84 bounding box."""
    try:
        query = FacilityQuery.parse(bbox)
    except ValueError as exc:
        raise HTTPException(422, "Ungültige Bounding Box.") from exc
    return service.list_facilities(query)


@router.get("/traffic")
def list_map_traffic(
    user: dict = Depends(get_current_user),
    service: MultiplayerMapService = Depends(get_multiplayer_map_service),
) -> dict:
    """Return the minimal live transport projection visible to all players."""
    return {"transports": service.list_traffic(user["id"])}
