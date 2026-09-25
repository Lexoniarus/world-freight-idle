"""Authenticated location projection for the map-first interface."""

import time

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import (
    get_current_user,
    get_map_service,
    get_traffic_reader,
)
from app.api.v1.location_projection import project_location
from app.api.v1.traffic_projection import project_traffic
from app.domain.read_ports import TrafficReader
from app.domain.world import FacilityQuery
from app.services.map_locations import MapLocationService

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/facilities/{identifier}")
def exact_facility(
    identifier: str,
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Resolve a session-bound legacy link using one exact reference."""
    try:
        return project_location(service.exact_facility(identifier))
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "Standort nicht gefunden.") from exc


@router.get("/cities/{city_uid}")
def exact_city(
    city_uid: str,
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Return only the requested city identity for authenticated navigation."""
    try:
        city = service.exact_city(city_uid)
    except (KeyError, ValueError) as exc:
        raise HTTPException(404, "Stadt nicht gefunden.") from exc
    return {
        "city_uid": city.city_uid,
        "city": city.name,
        "country": city.country.code,
    }


@router.get("/hubs")
async def list_map_hubs(
    service: MapLocationService = Depends(get_map_service),
) -> dict:
    """Project verified public facilities without external lookups."""
    return {
        "hubs": [
            project_location(location)
            for location in service.list_facilities(FacilityQuery()).facilities
        ]
    }


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
    page = service.list_facilities(query)
    return {
        "facilities": [
            project_location(location) for location in page.facilities
        ],
        "catalogue_version": page.catalogue_version,
        "unavailable_count": page.unavailable_count,
    }


@router.get("/traffic")
def list_map_traffic(
    user: dict = Depends(get_current_user),
    reader: TrafficReader = Depends(get_traffic_reader),
) -> dict:
    """Return the minimal live transport projection visible to all players."""
    return {
        "transports": project_traffic(
            reader.list_active_transports(time.time()), user["id"]
        )
    }
