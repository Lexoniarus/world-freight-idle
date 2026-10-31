"""Keep injected game clocks coherent in deterministic tests."""

from collections.abc import Callable

from app.services.gameplay.game import GameService
from app.services.market_route_preparation import (
    MarketRoutePreparationService,
)


def set_game_clock(
    synthetic_game: GameService,
    clock: Callable[[], float],
    route_preparation: MarketRoutePreparationService | None = None,
) -> None:
    """Replace every player workflow clock for one test-scoped game."""
    synthetic_game.now = clock
    synthetic_game.market_lifecycle.clock = clock
    synthetic_game.settlement.clock = clock
    synthetic_game.transport_dispatch.clock = clock
    synthetic_game.market_services.demand.clock = clock
    synthetic_game.market_services.routes.readiness.clock = clock
    if route_preparation is not None:
        route_preparation.clock = clock
        route_preparation.evidence.clock = clock
        route_preparation.preparation.clock = clock
