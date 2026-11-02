"""Preparation status persistence and local runtime composition."""

import pytest

from tests.support.market import (
    build_prepared_game,
    require_value,
)


def test_preparation_store_generation_and_reference_rollback(
    synthetic_game, database
):
    synthetic_game, preparation = build_prepared_game(synthetic_game, database)
    assert preparation.demand.jobs.status("missing") is None
    with pytest.raises(ValueError, match="publication"):
        preparation.routes.bind(synthetic_game.state_repository.list_offers())
    preparation.demand.ensure()
    first = require_value(preparation.demand.jobs.status("test-owner"))
    assert synthetic_game.preparation_status() == first
    preparation.demand.jobs.finish(
        "test-owner", "obsolete", "ready", None, synthetic_game.now()
    )
    assert preparation.demand.jobs.status("test-owner") == first
    preparation.demand.jobs.finish(
        "test-owner", first.generation, "ready", None, synthetic_game.now()
    )
    assert preparation.demand.jobs.next_player(synthetic_game.now()) is None
    preparation.demand.jobs.request(
        "test-owner", "new-generation", synthetic_game.now()
    )
    assert (
        require_value(preparation.demand.jobs.status("test-owner")).status
        == "partial"
    )


def test_preparation_composition_uses_complete_local_runtime(
    synthetic_game,
    synthetic_runtime,
):
    from app.bootstrap import (
        build_player_market_services,
        build_preparation_worker,
    )

    bound = build_player_market_services(synthetic_runtime, "test-owner")
    assert bound.demand.user_id == "test-owner"
    worker = build_preparation_worker(synthetic_runtime)
    from app.services.market.stock.preparation import StockPreparationBatch

    batch = worker.batches("test-owner")
    assert isinstance(batch, StockPreparationBatch)
    assert batch.publication.player_demand.user_id == "test-owner"
