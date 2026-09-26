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
from app.services.game import GameService

router = APIRouter(prefix="/contracts", tags=["contracts"])

ROUTING_FAILURE_DETAIL = "Straßenroute konnte nicht berechnet werden."


@router.get("")
def list_contracts(
    game: GameService = Depends(get_game_service),
) -> dict:
    """Return the active idle-vehicle city markets."""
    return {
        "contracts": [
            project_contract(item)
            for item in game.contract_choices(game.list_contracts())
        ]
    }


@router.get("/{contract_id}")
def get_contract(
    contract_id: str,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Return one contract including real endpoint addresses."""
    try:
        return project_contract(
            game.contract_choices((game.get_contract(contract_id),))[0]
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/{contract_id}/quote")
async def quote_contract(
    contract_id: str,
    body: QuoteRequest,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Route saved coordinates and return a provider-backed truck quote."""
    try:
        return project_quote(
            await game.quote_contract(contract_id, body.vehicle_id)
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RoutingError as exc:
        raise HTTPException(502, ROUTING_FAILURE_DETAIL) from exc


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
        raise HTTPException(502, ROUTING_FAILURE_DETAIL) from exc


@router.post("/refresh")
def refresh_contracts(
    game: GameService = Depends(get_game_service),
) -> dict:
    """Regenerate only the current active city markets."""
    return {
        "contracts": [
            project_contract(item)
            for item in game.contract_choices(game.refresh_contracts())
        ]
    }
