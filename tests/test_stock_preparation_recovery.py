"""Incremental stock preparation and reusable supply integration."""

from unittest.mock import patch

import pytest

from app.domain.market_preparation import required_relations
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from tests.support.game_clock import set_game_clock


@pytest.mark.asyncio
async def test_stale_evidence_reuses_offers_and_backoff_never_releases_stock(
    stock_game,
):
    game, prep, batch = stock_game
    now = [game.now()]
    set_game_clock(game, lambda: now[0], batch.route_preparation)
    prep.demand.clock = prep.routes.readiness.clock = lambda: now[0]
    batch.templates.clock = prep.demand.clock
    for _ in range(100):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    now[0] += 7 * 24 * 3600
    assert game.list_contracts()
    assert game.state_repository.list_offers() == saved
    with patch.object(
        prep.route_preparation.preparation.router,
        "route",
        side_effect=AssertionError("Ready routes must remain reusable"),
    ):
        assert game.list_contracts()
        await batch.process()
    assert game.state_repository.list_offers() == saved


@pytest.mark.asyncio
async def test_partial_connection_resumes_after_restart_and_never_releases_early(
    stock_game,
):
    from app.services.market.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
    target = next(
        t
        for t in batch.planning.targets(
            snapshot.demands, snapshot.candidates, snapshot.ready, ()
        )
    )
    remote = next(
        c
        for c in target.choices
        if c.trade.origin.facility_uid != target.demand.vehicle.facility_uid
    )
    with patch.object(type(batch), "_select", return_value=(target, remote)):
        await batch.process()
        assert game.state_repository.list_offers() == ()
        assert (
            sum(
                prep.routes.readiness.ready(*pair) is not None
                for pair in required_relations((remote,))
            )
            == 1
        )
        # Reopen the durable checkpoint and continue the other relation.
        prep.stores.offers = SqlitePlayerMarketStockStore(
            prep.stores.offers.database, prep.demand.user_id
        )
        assert prep.stores.offers.pending(target.key) == trade_key(remote)
        await batch.process()
    assert len(game.state_repository.list_offers()) == 1
    assert len(game.contract_choices(game.list_contracts(), "truck")) == 1
    assert prep.stores.offers.pending(target.key) is None
