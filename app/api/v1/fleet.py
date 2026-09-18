"""Fleet resource endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import (
    get_fleet_service,
    get_game_service,
    get_vehicle_catalogue,
)
from app.api.v1.schemas import PurchaseRequest
from app.domain.errors import CatalogueError
from app.domain.ports import VehicleCatalogue
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.vehicle_presentation import present_vehicles

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/catalogue")
def get_catalogue(fleet: FleetService = Depends(get_fleet_service)) -> dict:
    """List simulated vehicle models, prices and the fixed delivery hub."""
    try:
        return fleet.list_catalogue()
    except CatalogueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/purchase", status_code=201)
def purchase_vehicle(
    body: PurchaseRequest,
    fleet: FleetService = Depends(get_fleet_service),
    game: GameService = Depends(get_game_service),
) -> dict:
    """Purchase one vehicle for the authenticated player's fleet."""
    game.reconcile_arrival()
    try:
        vehicle = fleet.purchase(body.model_id)
    except CatalogueError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return game.get_vehicle(vehicle["id"])


@router.get("")
def list_fleet(
    game: GameService = Depends(get_game_service),
    catalogue: VehicleCatalogue = Depends(get_vehicle_catalogue),
) -> dict:
    """Return all player vehicles with their current real-world hub."""
    return {"vehicles": present_vehicles(game.list_vehicles(), catalogue)}


@router.get("/{vehicle_id}")
def get_vehicle(
    vehicle_id: str,
    game: GameService = Depends(get_game_service),
    catalogue: VehicleCatalogue = Depends(get_vehicle_catalogue),
) -> dict:
    """Return one player vehicle."""
    try:
        return present_vehicles([game.get_vehicle(vehicle_id)], catalogue)[0]
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
