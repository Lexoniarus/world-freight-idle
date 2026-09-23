"""Shared competitive rankings without private account information."""

import time

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user, get_leaderboard_reader
from app.domain.read_ports import LeaderboardReader

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
def get_leaderboard(
    user: dict = Depends(get_current_user),
    reader: LeaderboardReader = Depends(get_leaderboard_reader),
) -> dict:
    """Return the top 100 players by completed deliveries."""
    return {"players": reader.list_ranking(time.time())}
