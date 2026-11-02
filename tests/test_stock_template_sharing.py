"""Incremental stock preparation and reusable supply integration."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.services.market.player_demand import PlayerMarketDemandService
from app.services.market.player_routes import PlayerMarketRouteService
from app.services.market.player_services import PlayerMarketServices
from app.services.market.player_stock import PlayerMarketStockContext
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)
from app.services.market.stock.preparation import StockPreparationBatch
from app.services.market.stock.publication import StockPublicationService
from app.services.market.stock.snapshot import StockSnapshotReader


@pytest.mark.asyncio
async def test_templates_are_shared_but_consumption_is_once_per_account(
    stock_game, database
):
    from app.domain.game import PlayerState
    from app.repositories.game_state import SqliteGameUnitOfWork
    from app.repositories.routing_readiness import SqliteOfferRouteStore

    game, prep, batch = stock_game
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    templates = prep.stock.templates.templates(
        (game.get_vehicle("truck").location.city.city_uid,)
    )
    with database.transaction(), database.connect() as db:
        db.execute("INSERT INTO users VALUES ('other', 'Other', 'test', 0)")
        unit = SqliteGameUnitOfWork(database, "other")
        unit.repository.save_player(PlayerState(175000, 0, 0))
        unit.repository.save_vehicle(game.get_vehicle("truck"))
    other = PlayerMarketServices(
        PlayerMarketDemandService(
            "other",
            prep.demand.jobs,
            prep.demand.clock,
            database,
        ),
        PlayerMarketRouteService(
            prep.routes.readiness,
            SqliteOfferRouteStore(database, "other"),
            database,
        ),
        MarketRoutePreparationService(
            prep.routes.readiness,
            prep.route_preparation.preparation,
            prep.demand.clock,
        ),
        PlayerMarketStockContext(
            SqlitePlayerMarketStockStore(database, "other"),
            SqliteMarketTemplateStore(database),
        ),
    )
    other.demand.ensure()
    second = StockPreparationBatch(
        StockPublicationService(
            unit,
            game.market_lifecycle.market,
            other.demand,
            other.routes,
            other.stock,
            lambda: True,
        ),
        StockSnapshotReader(
            unit,
            game.market_lifecycle.market,
            other.demand,
            other.routes,
            other.stock,
            batch.snapshots.demand,
        ),
        batch.planning,
        batch.templates,
        other.route_preparation,
    )
    with patch.object(
        type(prep.route_preparation.preparation),
        "prepare",
        new=AsyncMock(
            side_effect=AssertionError("Cached roads must be reused")
        ),
    ):
        for _ in range(15):
            if (await second.process()).status == "ready":
                break
    assert (
        other.stock.templates.templates((templates[0].city_uid,)) == templates
    )
    common = next(
        iter(
            prep.stock.stock.bindings().keys()
            & other.stock.stock.bindings().keys()
        )
    )
    first_id, second_id = (
        prep.stock.stock.bindings()[common],
        other.stock.stock.bindings()[common],
    )
    assert first_id != second_id
    with database.transaction():
        prep.stock.stock.consume(first_id, game.now())
        with pytest.raises(ValueError, match="bereits verwendet"):
            prep.stock.stock.consume(first_id, game.now())
    assert common not in other.stock.stock.used()
    with database.transaction():
        other.stock.stock.consume(second_id, game.now())
    assert common in other.stock.stock.used()
    existing = next(
        o for o in game.state_repository.list_offers() if o.id == first_id
    )
    with pytest.raises(ValueError, match="bereits verwendet"):
        prep.stock.stock.issue(common, replace(existing, id="must-not-exist"))
    assert all(
        o.id != "must-not-exist" for o in game.state_repository.list_offers()
    )
