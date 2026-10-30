"""Keep injected game clocks coherent in deterministic tests."""

from collections.abc import Callable

from app.services.game import GameService
from app.services.market_route_preparation import (
    MarketRoutePreparationService,
)


def set_game_clock(
    game: GameService,
    clock: Callable[[], float],
    route_preparation: MarketRoutePreparationService | None = None,
) -> None:
    """Replace every player workflow clock for one test-scoped game."""
    game.now = clock
    game.market_lifecycle.clock = clock
    game.settlement.clock = clock
    game.transport_dispatch.clock = clock
    game.market_services.demand.clock = clock
    game.market_services.routes.readiness.clock = clock
    if route_preparation is not None:
        route_preparation.clock = clock
