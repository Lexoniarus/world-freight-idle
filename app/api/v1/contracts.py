"""Contract market endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import get_game_service
from app.api.v1.game_projection import (
    project_contract,
    project_quote,
    project_transport,
)
from app.api.v1.schemas import DispatchRequest, QuoteRequest
from app.domain.errors import RoutingError
from app.domain.world import FacilityQuery
from app.services.game import GameService

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
def list_contracts(
    bbox: str | None = None,
    zoom: float | None = None,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Return the idle-truck plus zoom-enabled viewport market."""
    try:
        query = FacilityQuery.parse(bbox)
    except ValueError as exc:
        raise HTTPException(422, "Ungültige Bounding Box.") from exc
    return {
        "contracts": [
            project_contract(item) for item in game.list_contracts(query, zoom)
        ]
    }


@router.get("/{contract_id}")
def get_contract(
    contract_id: str,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Return one contract including real endpoint addresses."""
    try:
        return project_contract(game.get_contract(contract_id))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{contract_id}/quote")
async def quote_contract(
    contract_id: str,
    body: QuoteRequest | None = None,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Route saved coordinates and return a provider-backed truck quote."""
    try:
        return project_quote(
            await game.quote_contract(
                contract_id, body.vehicle_id if body else None
            )
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/{contract_id}/accept")
async def accept_contract(
    contract_id: str,
    body: DispatchRequest,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Accept and dispatch one contract with a selected vehicle."""
    try:
        return project_transport(
            await game.dispatch(contract_id, body.vehicle_id)
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/refresh")
def refresh_contracts(
    bbox: str | None = None,
    zoom: float | None = None,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Regenerate only the current idle-truck plus viewport market."""
    try:
        query = FacilityQuery.parse(bbox)
    except ValueError as exc:
        raise HTTPException(422, "Ungültige Bounding Box.") from exc
    return {
        "contracts": [
            project_contract(item)
            for item in game.refresh_contracts(query, zoom)
        ]
    }
