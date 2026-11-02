"""Incremental stock preparation and reusable supply integration."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from tests.support.game_clock import set_game_clock


@pytest.mark.asyncio
async def test_destination_stock_starts_at_dispatch_without_early_settlement(
    stock_game, database
):
    from unittest.mock import Mock

    from tests.transport_fixtures import add_transport

    game, prep, batch = stock_game
    now = game.now()
    trip = add_transport(game, departed_at=now, arrives_at=now + 7200)
    world = game.market_lifecycle.market.candidates.reference()
    output = world.facilities[0].nhm_profiles[0]
    updated = replace(
        world,
        facilities=tuple(
            replace(f, nhm_profiles=(*f.nhm_profiles, output))
            if f.facility_uid == trip.destination.facility_uid
            else f
            for f in world.facilities
        ),
    )
    reference = Mock(read=Mock(return_value=updated))
    game.market_lifecycle.market.candidates.world = reference
    prep.routes.readiness.world = reference
    clock = [trip.departed_at + 1]
    set_game_clock(game, lambda: clock[0], batch.route_preparation)
    prep.demand.clock = lambda: clock[0]
    batch.templates.clock = prep.demand.clock
    snapshot = batch.snapshots.read()
    arriving = next(d for d in snapshot.demands if d.transport_id)
    assert arriving.transport_id == trip.id
    assert arriving.vehicle.facility_uid == trip.destination.facility_uid
    assert game.get_vehicle("truck").facility_uid == trip.origin.facility_uid
    before = game.state_repository.get_player()
    for _ in range(35):
        if (await batch.process()).status == "ready":
            break
    prepared = game.state_repository.list_offers()
    assert prepared
    assert game.state_repository.get_player() == before
    assert game.get_vehicle("truck").status == "enroute"
    with pytest.raises(ValueError, match="einsatzbereites"):
        game.contract_choices(prepared, "truck")
    clock[0] = trip.arrives_at + 1
    assert game.reconcile_arrival()
    after = game.state_repository.get_player()
    assert not game.reconcile_arrival()
    assert game.state_repository.get_player() == after
    with patch.object(
        type(prep.route_preparation.preparation),
        "prepare",
        new=AsyncMock(side_effect=AssertionError("Runtime provider fallback")),
    ):
        choices = game.contract_choices(game.list_contracts(), "truck")
        assert choices
        assert set(c.offer.id for c in choices) <= {o.id for o in prepared}
        await game.dispatch(choices[0].offer.id, "truck")
