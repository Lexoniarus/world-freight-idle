"""Name the private market stock dependencies as one cohesive context."""

from dataclasses import dataclass

from app.domain.market_stock import (
    MarketTemplateStore,
    PlayerMarketStockStore,
    StockPolicy,
)


@dataclass(slots=True)
class PlayerMarketStores:
    """Expose private offers and shared templates for one player."""

    offers: PlayerMarketStockStore
    templates: MarketTemplateStore
    policy: StockPolicy = StockPolicy()
