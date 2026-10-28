"""Name the private market stock dependencies as one cohesive context."""

from dataclasses import dataclass

from app.domain.market_stock import (
    MarketTemplateStore,
    PlayerMarketStockStore,
    StockPolicy,
)


@dataclass(slots=True)
class PlayerMarketStockContext:
    """Hold private issuance and shared template stores for one player."""

    stock: PlayerMarketStockStore
    templates: MarketTemplateStore
    policy: StockPolicy = StockPolicy()
