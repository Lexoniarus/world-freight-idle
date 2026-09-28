"""Compact polling and separately authorized historical route geometry."""

import base64
import json
import time
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.api.v1.dependencies import (
    get_current_user,
    get_runtime_reader,
    get_runtime_view,
    get_vehicle_catalogue,
)
from app.api.v1.game_projection import (
    project_contract,
    project_player,
    project_vehicle,
)
from app.api.v1.location_projection import project_location
from app.api.v1.traffic_projection import project_traffic
from app.api.v1.vehicle_presentation import present_vehicles
from app.domain.ports import VehicleCatalogue
from app.domain.read_ports import SharedTransport
from app.domain.runtime_views import (
    RuntimeReader,
    RuntimeTransport,
    RuntimeView,
)
from app.services.runtime_views import RuntimeViewService

router = APIRouter(tags=["runtime"])


def route_reference(owner_id: str, trip_id: str) -> str:
    """Identify the owner and immutable transport geometry projection."""
    value = json.dumps([1, owner_id, trip_id], separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def parse_route_reference(value: str) -> tuple[str, str]:
    """Reject unsupported or malformed route identifiers before storage."""
    try:
        if not value or len(value) > 1024:
            raise ValueError("Invalid reference length")
        decoded = json.loads(
            base64.b64decode(
                value + "=" * (-len(value) % 4),
                altchars=b"-_",
                validate=True,
            )
        )
        if (
            not isinstance(decoded, list)
            or len(decoded) != 3
            or type(decoded[0]) is not int
            or decoded[0] != 1
            or any(not isinstance(v, str) or not v for v in decoded[1:])
        ):
            raise ValueError("Invalid reference fields")
        return decoded[1], decoded[2]
    except (ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(404, "Route nicht gefunden.") from exc


def project_runtime_transport(
    trip: RuntimeTransport,
    owner_id: str,
    now: float,
) -> dict[str, Any]:
    """Expose existing private scalar fields without coordinate duplication."""
    return {
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "route_ref": route_reference(owner_id, trip.id),
        "contract": project_contract(trip.contract),
        "origin": project_location(trip.origin),
        "destination": project_location(trip.destination),
        "start": project_location(trip.start),
        "journey": asdict(trip.journey),
        "progress": asdict(trip.journey.progress_at(now - trip.departed_at)),
        "distance_km": trip.distance_km,
        "approach_distance_km": trip.approach_distance_km,
        "delivery_distance_km": trip.distance_km - trip.approach_distance_km,
        "routing_duration_seconds": trip.routing_duration_seconds,
        "provider": trip.provider,
        "departed_at": trip.departed_at,
        "arrives_at": trip.arrives_at,
        "payout_eur": trip.payout_eur,
        "operating_cost_eur": trip.operating_cost_eur,
        "profit_eur": trip.payout_eur - trip.operating_cost_eur,
        "cost_breakdown": asdict(trip.cost_breakdown)
        if trip.cost_breakdown
        else None,
    }


def project_runtime(
    view: RuntimeView,
    owner_id: str,
    catalogue: VehicleCatalogue,
) -> dict[str, Any]:
    """Project a compact owner snapshot with current energy and server time."""
    state = view.state
    trips = {trip.vehicle_id: trip for trip in state.transports}
    vehicles = []
    for vehicle in state.vehicles:
        value = project_vehicle(vehicle)
        trip = trips.get(vehicle.id)
        if trip is not None and trip.journey.energy is not None:
            value["energy_level"] = trip.journey.progress_at(
                view.server_time - trip.departed_at
            ).energy_level
        vehicles.append(value)
    return {
        "server_time": view.server_time,
        "time_scale": view.time_scale,
        "player": project_player(state.player),
        "vehicles": present_vehicles(vehicles, catalogue),
        "transports": [
            project_runtime_transport(t, owner_id, view.server_time)
            for t in state.transports
        ],
        "idle_vehicles": sum(v.status == "idle" for v in state.vehicles),
        "active_transports": len(state.transports),
        "market_preparation": asdict(view.preparation)
        if view.preparation
        else None,
    }


def project_traffic_summary(
    rows: tuple[SharedTransport, ...],
    viewer_id: str,
) -> list[dict[str, Any]]:
    """Keep the established public scalar contract with geometry references."""
    values = project_traffic(rows, viewer_id)
    for value, row in zip(values, rows):
        value.pop("route_geojson")
        value.pop("route_legs")
        value["route_ref"] = route_reference(row.user_id, row.id)
    return values


@router.get("/runtime")
def get_runtime(
    user: dict = Depends(get_current_user),
    service: RuntimeViewService = Depends(get_runtime_view),
    catalogue: VehicleCatalogue = Depends(get_vehicle_catalogue),
) -> dict:
    """Load playable owner state independently of map and market downloads."""
    return project_runtime(service.read(), user["id"], catalogue)


@router.get("/map/routes/{route_ref}")
def get_route_geometry(
    route_ref: str,
    request: Request,
    user: dict = Depends(get_current_user),
    reader: RuntimeReader = Depends(get_runtime_reader),
) -> Response:
    """Serve one authorized immutable geometry, including conditional reads."""
    owner_id, trip_id = parse_route_reference(route_ref)
    if not reader.visible(owner_id, trip_id, user["id"], time.time()):
        raise HTTPException(404, "Route nicht gefunden.")
    headers = {
        "ETag": f'W/"{route_ref}"',
        "Cache-Control": "private, no-cache",
    }
    if headers["ETag"] in request.headers.get("if-none-match", "").split(", "):
        return Response(status_code=304, headers=headers)
    try:
        geometry = reader.geometry(owner_id, trip_id)
    except KeyError as exc:
        raise HTTPException(404, "Route nicht gefunden.") from exc
    return JSONResponse(asdict(geometry), headers=headers)
