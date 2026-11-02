"""Shared market templates and account-scoped consumption."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.game import PlayerState
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.repositories.market_templates import SqliteMarketTemplateStore
from app.repositories.routing_readiness import SqliteOfferRouteStore
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


async def _prepare_shared_account_stock(stock_game, database):
    game, preparation, batch = stock_game
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    templates = preparation.stock.templates.templates(
        (game.get_vehicle("truck").location.city.city_uid,)
    )
    with database.transaction(), database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('other', 'Other', 'test', 0)"
        )
        unit = SqliteGameUnitOfWork(database, "other")
        unit.repository.save_player(PlayerState(175000, 0, 0))
        unit.repository.save_vehicle(game.get_vehicle("truck"))

    other = PlayerMarketServices(
        PlayerMarketDemandService(
            "other",
            preparation.demand.jobs,
            preparation.demand.clock,
            database,
        ),
        PlayerMarketRouteService(
            preparation.routes.readiness,
            SqliteOfferRouteStore(database, "other"),
            database,
        ),
        MarketRoutePreparationService(
            preparation.routes.readiness,
            preparation.route_preparation.preparation,
            preparation.demand.clock,
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
        type(preparation.route_preparation.preparation),
        "prepare",
        new=AsyncMock(
            side_effect=AssertionError("Cached roads must be reused")
        ),
    ):
        for _ in range(15):
            if (await second.process()).status == "ready":
                break
    return game, preparation, other, templates


@pytest.mark.asyncio
async def test_templates_are_shared_without_new_provider_calls(
    stock_game,
    database,
):
    game, preparation, other, templates = await _prepare_shared_account_stock(
        stock_game,
        database,
    )

    city_uid = templates[0].city_uid
    assert other.stock.templates.templates((city_uid,)) == templates
    common = next(
        iter(
            preparation.stock.stock.bindings().keys()
            & other.stock.stock.bindings().keys()
        )
    )
    first_id = preparation.stock.stock.bindings()[common]
    second_id = other.stock.stock.bindings()[common]
    assert first_id != second_id
    assert game.get_vehicle("truck").location.city.city_uid == city_uid


@pytest.mark.asyncio
async def test_template_consumption_is_once_per_account(stock_game, database):
    game, preparation, other, _ = await _prepare_shared_account_stock(
        stock_game,
        database,
    )
    common = next(
        iter(
            preparation.stock.stock.bindings().keys()
            & other.stock.stock.bindings().keys()
        )
    )
    first_id = preparation.stock.stock.bindings()[common]
    second_id = other.stock.stock.bindings()[common]

    with database.transaction():
        preparation.stock.stock.consume(first_id, game.now())
        with pytest.raises(ValueError, match="bereits verwendet"):
            preparation.stock.stock.consume(first_id, game.now())
    assert common not in other.stock.stock.used()
    with database.transaction():
        other.stock.stock.consume(second_id, game.now())
    assert common in other.stock.stock.used()


@pytest.mark.asyncio
async def test_used_template_cannot_issue_a_second_bound_offer(
    stock_game,
    database,
):
    game, preparation, other, _ = await _prepare_shared_account_stock(
        stock_game,
        database,
    )
    common = next(
        iter(
            preparation.stock.stock.bindings().keys()
            & other.stock.stock.bindings().keys()
        )
    )
    first_id = preparation.stock.stock.bindings()[common]
    with database.transaction():
        preparation.stock.stock.consume(first_id, game.now())
    existing = next(
        offer
        for offer in game.state_repository.list_offers()
        if offer.id == first_id
    )

    duplicate = replace(existing, id="must-not-exist")
    with pytest.raises(ValueError, match="bereits verwendet"):
        preparation.stock.stock.issue(common, duplicate)
    assert all(
        offer.id != "must-not-exist"
        for offer in game.state_repository.list_offers()
    )
