"""Atomic dispatch behavior at the prepared city-market boundary."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.services.gameplay.fleet import build_owned_vehicle
from tests.support.game import other_facility_offer


async def test_same_city_dispatch_preserves_departure_and_invalidates_demand(
    synthetic_game,
):
    offer = other_facility_offer(synthetic_game)
    before = synthetic_game.get_vehicle("truck_01")
    quote = await synthetic_game.quote_contract(offer.id, before.id)
    trip = await synthetic_game.dispatch(offer.id, before.id)
    vehicle = synthetic_game.get_vehicle(before.id)
    assert vehicle.facility_uid == before.facility_uid
    assert vehicle.location == before.location == trip.dispatch_route.start
    assert trip.origin == offer.origin
    assert vehicle.status == "enroute"
    assert trip.journey == quote.journey
    assert trip.operating_cost_eur == quote.economics.operating_cost_eur
    assert vehicle.energy_level == before.energy_level
    assert offer.id not in {
        item.id for item in synthetic_game.state_repository.list_offers()
    }
    assert synthetic_game.list_contracts() == []


async def test_dispatch_failure_rolls_back_reservation_and_market(
    synthetic_game,
):
    offer = other_facility_offer(synthetic_game)
    before_vehicle = synthetic_game.get_vehicle("truck_01")
    before_cash = synthetic_game.player_state().cash
    before_offers = synthetic_game.state_repository.list_offers()
    with patch.object(
        synthetic_game.state_repository,
        "save_transport",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            await synthetic_game.dispatch(offer.id, "truck_01")
    assert synthetic_game.get_vehicle("truck_01").location == (
        before_vehicle.location
    )
    assert synthetic_game.get_vehicle("truck_01").status == "idle"
    assert synthetic_game.player_state().cash == before_cash
    assert synthetic_game.state_repository.list_offers() == before_offers
    assert synthetic_game.state_repository.list_active_transports() == ()


async def test_dispatch_commits_before_followup_market_reads(synthetic_game):
    offer = other_facility_offer(synthetic_game)
    cash = synthetic_game.player_state().cash
    trip = await synthetic_game.dispatch(offer.id, "truck_01")
    assert synthetic_game.get_vehicle("truck_01").status == "enroute"
    assert synthetic_game.get_vehicle("truck_01").location == (
        trip.dispatch_route.start
    )
    assert synthetic_game.player_state().cash == cash - trip.operating_cost_eur
    assert synthetic_game.state_repository.list_active_transports() == (trip,)
    assert offer.id not in {
        item.id for item in synthetic_game.state_repository.list_offers()
    }
    assert synthetic_game.list_contracts() == []


async def test_dispatch_retains_stock_for_another_idle_vehicle(
    synthetic_game_context,
    synthetic_game,
):
    offer = other_facility_offer(synthetic_game)
    first = synthetic_game.get_vehicle("truck_01")
    model = next(
        item
        for item in synthetic_game_context.catalogue.list_models()
        if item.id == first.model_id
    )
    second = build_owned_vehicle(model, "second", first.location)
    synthetic_game.state_repository.save_vehicle(second)
    trip = await synthetic_game.dispatch(offer.id, first.id)
    assert synthetic_game.state_repository.list_active_transports() == (trip,)
    remaining = synthetic_game.state_repository.list_offers()
    assert offer.id not in {item.id for item in remaining}
    assert remaining
    assert synthetic_game.list_contracts() == list(remaining)


async def test_dispatch_restores_only_the_exact_saved_vehicle_location(
    synthetic_game,
):
    offer = other_facility_offer(synthetic_game)
    vehicle = synthetic_game.get_vehicle("truck_01")
    location = vehicle.location
    assert location is not None
    with pytest.raises(ValueError, match="stored facility"):
        vehicle.restore_location(offer.origin)
    changed = replace(location, label="Changed reference name")
    with pytest.raises(ValueError, match="existing location"):
        vehicle.restore_location(changed)
    vehicle.restore_location(location)
    vehicle._location = None
    synthetic_game.state_repository.save_vehicle(vehicle)
    await synthetic_game.quote_contract(offer.id, vehicle.id)
    assert synthetic_game.get_vehicle(vehicle.id).location is None
    trip = await synthetic_game.dispatch(offer.id, vehicle.id)
    assert synthetic_game.get_vehicle(vehicle.id).location == location
    assert trip.dispatch_route.start == location


async def test_quote_rejects_changed_capabilities_and_missing_saved_cost(
    synthetic_game_context,
    synthetic_game,
):
    offer = synthetic_game.list_contracts()[0]
    vehicle = synthetic_game.get_vehicle("truck_01")
    quote = await synthetic_game.quote_contract(offer.id, vehicle.id)
    vehicle._operating_cost_eur_per_km = None
    assert synthetic_game.transport_dispatch.calculate_quote(
        offer,
        quote.dispatch_route,
        vehicle,
    ).economics == quote.economics
    model = next(
        item
        for item in synthetic_game_context.catalogue.list_models()
        if item.id == vehicle.model_id
    )
    unsupported = replace(
        model,
        transport_capabilities=tuple(
            replace(capability, suitability_game=0)
            for capability in model.transport_capabilities
        ),
    )
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        return_value=(unsupported,),
    ):
        with pytest.raises(ValueError, match="Transportklasse"):
            await synthetic_game.quote_contract(offer.id, vehicle.id)
        with pytest.raises(ValueError, match="Transportklasse"):
            await synthetic_game.dispatch(offer.id, vehicle.id)
        assert not synthetic_game.list_contracts()
    assert not synthetic_game.state_repository.list_active_transports()
