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
from app.services.market.player_stores import PlayerMarketStores
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
    templates = preparation.stores.templates.templates(
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
        PlayerMarketStores(
            SqlitePlayerMarketStockStore(database, "other"),
            SqliteMarketTemplateStore(database),
        ),
    )
    other.demand.ensure()
    second = StockPreparationBatch(
        StockPublicationService(
            unit,
            game.market_lifecycle.generation,
            other.demand,
            other.routes,
            other.stores,
            lambda: True,
        ),
        StockSnapshotReader(
            unit,
            game.market_lifecycle.generation,
            other.demand,
            other.routes,
            other.stores,
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
    assert other.stores.templates.templates((city_uid,)) == templates
    common = next(
        iter(
            preparation.stores.offers.bindings().keys()
            & other.stores.offers.bindings().keys()
        )
    )
    first_id = preparation.stores.offers.bindings()[common]
    second_id = other.stores.offers.bindings()[common]
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
            preparation.stores.offers.bindings().keys()
            & other.stores.offers.bindings().keys()
        )
    )
    first_id = preparation.stores.offers.bindings()[common]
    second_id = other.stores.offers.bindings()[common]

    with database.transaction():
        preparation.stores.offers.consume(first_id, game.now())
        with pytest.raises(ValueError, match="bereits verwendet"):
            preparation.stores.offers.consume(first_id, game.now())
    assert common not in other.stores.offers.used()
    with database.transaction():
        other.stores.offers.consume(second_id, game.now())
    assert common in other.stores.offers.used()


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
            preparation.stores.offers.bindings().keys()
            & other.stores.offers.bindings().keys()
        )
    )
    first_id = preparation.stores.offers.bindings()[common]
    with database.transaction():
        preparation.stores.offers.consume(first_id, game.now())
    existing = next(
        offer
        for offer in game.state_repository.list_offers()
        if offer.id == first_id
    )

    duplicate = replace(existing, id="must-not-exist")
    with pytest.raises(ValueError, match="bereits verwendet"):
        preparation.stores.offers.issue(common, duplicate)
    assert all(
        offer.id != "must-not-exist"
        for offer in game.state_repository.list_offers()
    )
