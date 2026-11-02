"""Bounded market-route preparation independently of worker lifecycle."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.domain.market_preparation import required_relations
from app.services.market.route_preparation import (
    MarketRoutePreparationService,
)


def first_candidate(synthetic_game_context, synthetic_game):
    owned = synthetic_game.state_repository.list_vehicles()
    fleet = synthetic_game_context.market_generation.candidates.resolve_fleet(
        owned
    )
    return synthetic_game_context.market_generation.candidates.build(
        synthetic_game_context.market_scope.resolve(owned),
        fleet,
    )[0]


@pytest.mark.asyncio
async def test_route_preparation_bounds_provider_work_and_reports_retry(
    synthetic_game_context,
    synthetic_game,
):
    candidate = first_candidate(synthetic_game_context, synthetic_game)
    pairs = required_relations((candidate,))
    evidence = Mock()
    evidence.current.return_value = None
    preparation = AsyncMock()
    preparation.prepare.return_value = None
    service = MarketRoutePreparationService(evidence, preparation, lambda: 10)

    complete, retry_at = await service.prepare((candidate,), limit=1)

    assert pairs
    assert not complete
    assert retry_at == 11
    assert preparation.prepare.await_count == 1


@pytest.mark.asyncio
async def test_route_preparation_reuses_ready_evidence(
    synthetic_game_context,
    synthetic_game,
):
    candidate = first_candidate(synthetic_game_context, synthetic_game)
    evidence = Mock()
    evidence.current.return_value = SimpleNamespace(status="ready")
    preparation = AsyncMock()
    service = MarketRoutePreparationService(evidence, preparation, lambda: 10)

    complete, retry_at = await service.prepare((candidate,))

    assert complete
    assert retry_at is None
    preparation.prepare.assert_not_awaited()
