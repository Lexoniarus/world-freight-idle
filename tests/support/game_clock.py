"""Keep injected game clocks coherent in deterministic tests."""

from collections.abc import Callable

from app.services.game import GameService


def set_game_clock(game: GameService, clock: Callable[[], float]) -> None:
    """Replace every player workflow clock for one test-scoped game."""
    game.now = clock
    game.market_lifecycle.clock = clock
    game.settlement.clock = clock
    game.transport_dispatch.clock = clock
    if game.market_lifecycle.demand is not None:
        game.market_lifecycle.demand.clock = clock
    if game.market_lifecycle.routes is not None:
        game.market_lifecycle.routes.clock = clock
