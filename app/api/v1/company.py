"""Session-bound company statistics with existing arrival reconciliation."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.dependencies import get_current_user, get_game_service
from app.bootstrap import build_analytics_service
from app.services.analytics import validate_scope
from app.services.game import GameService

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/analytics")
def get_analytics(
    request: Request,
    days: str = "30",
    scope: str = "company",
    scope_id: str | None = None,
    user: dict = Depends(get_current_user),
    game: GameService = Depends(get_game_service),
) -> dict[str, Any]:
    """Reconcile due arrivals, then use the independent read model."""
    try:
        validate_scope(days, scope, scope_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    game.reconcile_arrival()
    return build_analytics_service(request.app.state.game, user["id"]).analyze(
        game.now(),
        days,
        scope,
        scope_id,
    )
