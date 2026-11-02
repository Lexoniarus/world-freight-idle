"""Compose independent player-market responsibilities."""

from dataclasses import dataclass

from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)


@dataclass(slots=True)
class PlayerMarketServices:
    """Expose explicit player-market capabilities to the composition root."""

    demand: PlayerMarketDemandService
    routes: PlayerMarketRouteService
    route_preparation: MarketRoutePreparationService
    stock: PlayerMarketStockContext
