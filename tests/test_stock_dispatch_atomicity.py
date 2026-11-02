"""Incremental stock preparation and reusable supply integration."""

from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_parallel_dispatch_consumes_one_template_and_debits_once(
    stock_game,
):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.repositories.game_state import SqliteGameUnitOfWork
    from app.services.gameplay.dispatch import TransportDispatchService
    from app.services.gameplay.game import GameService
    from app.services.gameplay.initialization import (
        PlayerInitializationService,
    )
    from app.services.gameplay.settlement import TransportSettlementService
    from app.services.gameplay.vehicle_location import VehicleLocationResolver
    from app.services.market.lifecycle import MarketLifecycleService

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    offer = game.contract_choices(game.list_contracts(), "truck")[0].offer
    unit = SqliteGameUnitOfWork(
        prep.stock.stock.database,
        prep.demand.user_id,
    )
    lifecycle = MarketLifecycleService(
        unit,
        game.market_lifecycle.market,
        game.market_lifecycle.scope,
        game.now,
        prep.demand,
        prep.routes,
        prep.stock,
        selection=game.market_lifecycle.selection,
    )
    settlement = TransportSettlementService(
        unit,
        game.now,
        prep.demand,
    )
    dispatch_service = TransportDispatchService(
        unit,
        game.market_lifecycle.market,
        game.transport_dispatch.planning,
        game.transport_dispatch.eligibility,
        VehicleLocationResolver(game.market_lifecycle.scope.world),
        settlement,
        game.now,
        game.time_scale,
        prep.demand,
        prep.stock,
    )
    other = GameService(
        unit,
        game.now,
        game.time_scale,
        lifecycle,
        PlayerInitializationService(
            unit,
            game.market_lifecycle.scope.world,
            game.market_lifecycle.market.candidates.catalogue,
            prep.demand,
        ),
        settlement,
        dispatch_service,
        prep,
    )
    barrier = Barrier(2)
    original = TransportDispatchService.quote_contract

    async def together(service, contract_id, vehicle_id):
        quote = await original(service, contract_id, vehicle_id)
        barrier.wait(timeout=10)
        return quote

    def run_dispatch(service):
        try:
            return asyncio.run(service.dispatch(offer.id, "truck"))
        except (ValueError, KeyError) as error:
            return error

    before = game.state_repository.get_player().cash
    with (
        patch.object(TransportDispatchService, "quote_contract", new=together),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [
            pool.submit(run_dispatch, service) for service in (game, other)
        ]
        results = [f.result() for f in futures]
    assert sum(isinstance(r, (ValueError, KeyError)) for r in results) == 1
    trips = game.state_repository.list_active_transports()
    assert len(trips) == len(prep.stock.stock.used()) == 1
    assert game.state_repository.get_player().cash == (
        before - trips[0].operating_cost_eur
    )
