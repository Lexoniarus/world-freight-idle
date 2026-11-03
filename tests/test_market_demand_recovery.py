"""Demand invalidation and deterministic route exhaustion."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.errors import RoutingError
from tests.support.market import (
    build_prepared_game,
    make_stock_batch,
    require_value,
)


@pytest.mark.asyncio
async def test_exhausted_negative_demand_requires_explicit_invalidation(
    synthetic_game_context,
    database,
):
    prepared_context, preparation = build_prepared_game(
        synthetic_game_context, database
    )
    synthetic_game = prepared_context.service
    owned = synthetic_game.state_repository.list_vehicles()
    fleet = synthetic_game_context.market_generation.candidates.resolve_fleet(
        owned
    )
    candidate = synthetic_game_context.market_generation.candidates.build(
        synthetic_game_context.market_scope.resolve(owned),
        fleet,
    )[0]
    pair = (
        candidate.trade.origin.facility_uid,
        candidate.trade.destination.facility_uid,
    )
    readiness = preparation.routes.readiness
    routing = preparation.route_preparation.preparation
    error = RoutingError("No path")
    error.category = "no_path"
    routing.router = AsyncMock()
    routing.router.route.side_effect = error
    await routing.prepare(*pair)
    preparation.demand.ensure()
    status = require_value(preparation.demand.jobs.status("test-owner"))
    preparation.demand.jobs.finish(
        "test-owner",
        status.generation,
        "exhausted",
        None,
        synthetic_game.now(),
    )
    preparation.demand.ensure()
    assert preparation.demand.jobs.next_player(synthetic_game.now()) is None
    before = preparation.routes.demand_state(*pair)
    readiness.provider_revision = lambda: "new-graph"
    after = preparation.routes.demand_state(*pair)
    assert after.expected_fingerprint != before.expected_fingerprint
    preparation.demand.invalidate()
    changed = require_value(preparation.demand.jobs.status("test-owner"))
    assert changed.generation != status.generation
    assert changed.status == "partial"
    assert (
        preparation.demand.jobs.next_player(synthetic_game.now())
        == "test-owner"
    )
    await routing.prepare(*pair)
    assert routing.router.route.await_count == 2


@pytest.mark.asyncio
async def test_batch_exhausts_deterministic_route_failures(
    synthetic_game_context,
    database,
):
    prepared_context, preparation = build_prepared_game(
        synthetic_game_context, database
    )
    synthetic_game = prepared_context.service
    batch = make_stock_batch(synthetic_game, preparation)
    owned = synthetic_game.state_repository.list_vehicles()
    fleet = synthetic_game_context.market_generation.candidates.resolve_fleet(
        owned
    )
    candidates = synthetic_game_context.market_generation.candidates.build(
        synthetic_game_context.market_scope.resolve(owned), fleet
    )[:2]
    synthetic_game_context.market_generation.candidates.build = Mock(
        return_value=candidates
    )
    error = RoutingError("No path")
    error.category = "no_path"
    routing = preparation.route_preparation.preparation
    routing.router = AsyncMock()
    routing.router.route.side_effect = error
    preparation.demand.ensure()
    result = await batch.process()
    for _ in range(10):
        result = await batch.process()
        if result.status == "exhausted":
            break
    assert result.status == "exhausted"
    assert synthetic_game.list_contracts() == []
