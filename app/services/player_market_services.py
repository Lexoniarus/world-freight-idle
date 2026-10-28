"""Compose independent player-market responsibilities."""

from dataclasses import dataclass

from app.services.player_market_demand import PlayerMarketDemandService
from app.services.player_market_routes import PlayerMarketRouteService
from app.services.player_market_stock import PlayerMarketStockContext


@dataclass(slots=True)
class PlayerMarketServices:
    """Expose explicit player-market capabilities to the composition root."""

    demand: PlayerMarketDemandService
    routes: PlayerMarketRouteService
    stock: PlayerMarketStockContext
