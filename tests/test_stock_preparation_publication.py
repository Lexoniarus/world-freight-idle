"""Incremental stock preparation and reusable supply integration."""

from unittest.mock import patch

import pytest

from app.domain.market_preparation import required_relations
from tests.support.game_clock import set_game_clock


@pytest.mark.asyncio
async def test_preparation_publishes_three_distinct_ready_trades(
    diverse_stock_game,
):
    """Expose ready structural variety through the public worker boundary."""
    game, preparation, batch = diverse_stock_game
    snapshot = batch.snapshots.read()
    ready_candidates = []
    signatures = set()
    for candidate in snapshot.candidates:
        if candidate.distance_profile.distance_band != "short":
            continue
        signature = (
            candidate.trade.origin.facility_uid,
            candidate.trade.destination.facility_uid,
            candidate.trade.cargo.nhm_row_id,
        )
        if signature in signatures:
            continue
        signatures.add(signature)
        ready_candidates.append(candidate)
        for pair in required_relations((candidate,)):
            await preparation.route_preparation.preparation.prepare(*pair)
        if len(ready_candidates) == 3:
            break
    assert len(ready_candidates) == 3

    observed_counts = [0]
    visible = ()
    for _ in range(20):
        await batch.process()
        visible = tuple(
            choice.offer
            for choice in game.contract_choices(
                game.list_contracts(),
                "truck",
            )
            if choice.offer.market_context is not None
            and choice.offer.market_context.distance_band == "short"
        )
        if not observed_counts or len(visible) != observed_counts[-1]:
            observed_counts.append(len(visible))
        if len(visible) == 3:
            break

    assert observed_counts == [0, 1, 2, 3]

    assert (
        len(
            {
                (
                    offer.origin.facility_uid,
                    offer.destination.facility_uid,
                    offer.cargo.nhm_row_id,
                )
                for offer in visible
            }
        )
        == 3
    )


@pytest.mark.asyncio
async def test_shared_stock_has_three_visible_ten_ready_and_does_not_expire(
    stock_game,
):
    game, prep, batch = stock_game
    build = game.market_lifecycle.generation.candidates.build

    def outside_writer(*args):
        assert prep.stores.offers.database._active.get() is None
        return build(*args)

    with patch.object(
        game.market_lifecycle.generation.candidates,
        "build",
        side_effect=outside_writer,
    ):
        result = await batch.process()
    for _ in range(100):
        result = await batch.process()
        if result.status == "ready":
            break
    assert result.status == "ready"
    offers = game.list_contracts()
    assert len(offers) == 30
    choices = game.contract_choices(offers, "truck")
    assert len(choices) == 9
    assert all(
        sum(c.offer.market_context.distance_band == band for c in choices) == 3
        for band in ("short", "medium", "long")
    )
    assert all(o.expires_at is None for o in offers)
    assert (
        len(prep.stores.templates.templates((offers[0].origin.city.city_uid,)))
        == 30
    )
    assert game.refresh_contracts() == offers
    assert game.list_contracts() == offers
    ids = [o.id for o in offers]
    future = game.now() + 7 * 3600
    set_game_clock(game, lambda: future, batch.route_preparation)
    assert [o.id for o in game.list_contracts()] == ids
    chosen = choices[0].offer
    before = set(prep.stores.offers.bindings())
    await game.dispatch(chosen.id, "truck")
    assert len(prep.stores.offers.used()) == 1
    assert prep.stores.offers.used() <= before
    assert len(game.state_repository.list_offers()) == 29
    # Departure hides availability but does not delete the reserve.
    assert game.list_contracts() == []
    await batch.process()
    assert len(game.state_repository.list_offers()) == 29
    status = prep.demand.jobs.status(prep.demand.user_id)
    prep.demand.jobs.finish(
        prep.demand.user_id,
        status.generation,
        "ready",
        game.now() + 60,
        game.now(),
    )
    ready_status = prep.demand.jobs.status(prep.demand.user_id)
    assert game.list_contracts() == []
    assert prep.demand.jobs.status(prep.demand.user_id) == ready_status
