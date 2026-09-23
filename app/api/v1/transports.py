"""Live transport tracking endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.v1.dependencies import get_game_service
from app.api.v1.game_projection import project_transport
from app.services.game import GameService

router = APIRouter(prefix="/transports", tags=["transports"])


@router.get("")
def list_transports(game: GameService = Depends(get_game_service)) -> dict:
    """Return active and recent transport state for the MVP."""
    return {
        "transports": [
            project_transport(item) for item in game.list_transports()
        ]
    }


@router.get("/{transport_id}")
def get_transport(
    transport_id: str,
    game: GameService = Depends(get_game_service),
) -> dict:
    """Return one live transport including route geometry and timestamps."""
    try:
        return project_transport(game.get_transport(transport_id))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
