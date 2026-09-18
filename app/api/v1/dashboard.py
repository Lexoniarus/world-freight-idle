"""Dashboard resource endpoints."""

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_game_service
from app.services.game import GameService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(game: GameService = Depends(get_game_service)) -> dict:
    """Return the compact dashboard view model."""
    return game.dashboard()
