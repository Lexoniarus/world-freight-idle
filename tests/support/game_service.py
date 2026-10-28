"""Explicit test-only composition helpers for player game services."""

from app.domain.state_ports import GameUnitOfWork
from app.services.game import GameService


def rebind_game_storage(
    game: GameService,
    unit_of_work: GameUnitOfWork,
) -> None:
    """Move every player-state service to one test-controlled repository."""
    game.unit_of_work = unit_of_work
    game.state_repository = unit_of_work.repository
    game.market_lifecycle.unit_of_work = unit_of_work
    game.initialization.unit = unit_of_work
    game.settlement.unit = unit_of_work
    game.transport_dispatch.unit = unit_of_work
