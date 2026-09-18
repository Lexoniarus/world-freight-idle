"""Shared competitive rankings without private account information."""

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_auth_service, get_current_user
from app.services.auth import AuthService

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
def get_leaderboard(
    user: dict = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Return the top 100 players by completed deliveries."""
    return {"players": auth.accounts.leaderboard()}
