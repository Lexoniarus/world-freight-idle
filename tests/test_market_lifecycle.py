"""Market v2 dispatch atomicity, refill isolation and history regression."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.economics import CostBreakdown
from app.domain.errors import CatalogueError
from app.domain.pricing import calculate_price
from app.repositories.snapshot_mapping import load_historical_contract
from app.services.gameplay.fleet import build_owned_vehicle
from tests.support.game import other_facility_offer
from tests.support.game_clock import set_game_clock


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
    assert (
        synthetic_game.get_vehicle("truck_01").location
        == before_vehicle.location
    )
    assert synthetic_game.get_vehicle("truck_01").status == "idle"
    assert synthetic_game.player_state().cash == before_cash
    assert synthetic_game.state_repository.list_offers() == before_offers
    assert synthetic_game.state_repository.list_active_transports() == ()


async def test_dispatch_commits_before_followup_market_reads(synthetic_game):
    offer = other_facility_offer(synthetic_game)
    cash = synthetic_game.player_state().cash
    assert not hasattr(synthetic_game.market_lifecycle.market, "generate")
    trip = await synthetic_game.dispatch(offer.id, "truck_01")
    assert synthetic_game.get_vehicle("truck_01").status == "enroute"
    assert (
        synthetic_game.get_vehicle("truck_01").location
        == trip.dispatch_route.start
    )
    assert synthetic_game.player_state().cash == cash - trip.operating_cost_eur
    assert synthetic_game.state_repository.list_active_transports() == (trip,)
    assert offer.id not in {
        item.id for item in synthetic_game.state_repository.list_offers()
    }
    assert synthetic_game.list_contracts() == []
    assert synthetic_game.state_repository.list_active_transports() == (trip,)
    assert synthetic_game.player_state().cash == cash - trip.operating_cost_eur


async def test_dispatch_retains_stock_for_another_idle_vehicle(
    synthetic_game_context, synthetic_game
):
    offer = other_facility_offer(synthetic_game)
    first = synthetic_game.get_vehicle("truck_01")
    model = next(
        m
        for m in synthetic_game_context.catalogue.list_models()
        if m.id == first.model_id
    )
    second = build_owned_vehicle(model, "second", first.location)
    synthetic_game.state_repository.save_vehicle(second)
    assert not hasattr(synthetic_game.market_lifecycle.market, "generate")
    trip = await synthetic_game.dispatch(offer.id, first.id)
    assert synthetic_game.state_repository.list_active_transports() == (trip,)
    remaining = synthetic_game.state_repository.list_offers()
    assert offer.id not in {o.id for o in remaining}
    assert remaining
    assert synthetic_game.list_contracts() == list(remaining)


async def test_arrival_activates_city_and_preserves_historical_terms(
    synthetic_game_context, synthetic_game, monkeypatch
):
    offer = next(
        o
        for o in synthetic_game.list_contracts()
        if o.destination.city.city_uid != o.origin.city.city_uid
    )
    build_trip = synthetic_game.transport_dispatch.build_trip

    def historical_trip(*args):
        trip = build_trip(*args)
        return replace(
            trip,
            contract=replace(
                trip.contract,
                market_model="nhm_v1",
                market_context=None,
                payload_band="heavy",
            ),
        )

    with patch.object(
        type(synthetic_game.transport_dispatch),
        "build_trip",
        lambda self, *args: historical_trip(*args),
    ):
        historical = await synthetic_game.dispatch(offer.id, "truck_01")
    trip = historical
    set_game_clock(synthetic_game, lambda: trip.arrives_at + 1)
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        assert synthetic_game.reconcile_arrival()
        assert not synthetic_game.reconcile_arrival()
    settled = synthetic_game.state_repository.list_transports()[0]
    assert settled.contract == historical.contract
    assert settled.payout_eur == trip.payout_eur
    assert synthetic_game.get_vehicle("truck_01").location == trip.destination
    offers = synthetic_game.list_contracts()
    assert offers == []


def test_retention_filters_without_writing_during_market_reads(
    synthetic_game_context, synthetic_game
):
    offers = synthetic_game.list_contracts()
    first = offers[0]
    legacy = replace(
        first, id="legacy", market_model="nhm_v1", market_context=None
    )
    expired = replace(
        first, id="expiring", expires_at=synthetic_game.now() + 30
    )
    synthetic_game.state_repository.replace_offers((*offers, legacy, expired))
    synthetic_game.market_services.routes.bind((*offers, legacy, expired))
    assert synthetic_game.list_contracts() == offers
    assert synthetic_game.contract_choices(offers)[0].eligible_vehicle_ids == (
        "truck_01",
    )
    vehicle = synthetic_game.get_vehicle("truck_01")
    vehicle._capacity_tons = 0.1
    synthetic_game.state_repository.save_vehicle(vehicle)
    new = synthetic_game.list_contracts()
    assert new == []
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        with pytest.raises(CatalogueError):
            synthetic_game.list_contracts()
    assert synthetic_game.state_repository.list_offers() == (
        *offers,
        legacy,
        expired,
    )


def test_reposition_rejects_busy_other_city_and_missing_location(
    synthetic_game,
):
    vehicle = synthetic_game.get_vehicle("truck_01")
    offer = next(
        o
        for o in synthetic_game.list_contracts()
        if o.destination.city.city_uid != vehicle.location.city.city_uid
    )
    with pytest.raises(ValueError, match="same city"):
        vehicle.reposition_within_city(offer.destination)
    vehicle.start_trip()
    with pytest.raises(ValueError, match="idle"):
        vehicle.reposition_within_city(offer.origin)
    vehicle.arrive(offer.origin)
    vehicle._location = None
    with pytest.raises(ValueError, match="same city"):
        vehicle.reposition_within_city(offer.origin)


def test_freight_rate_changes_payout_but_cargo_value_does_not(synthetic_game):
    offer = synthetic_game.list_contracts()[0]
    costs = CostBreakdown("test", 0.5, "diesel", "l", 1.5, 80, 200, (), 0, 280)
    base = calculate_price(offer.tons, 400, costs, offer.rate_eur_per_km_ton)
    assert (
        calculate_price(
            offer.tons, 800, costs, offer.rate_eur_per_km_ton
        ).payout_eur
        > base.payout_eur
    )
    assert (
        calculate_price(
            offer.tons * 2, 400, costs, offer.rate_eur_per_km_ton
        ).payout_eur
        > base.payout_eur
    )
    assert (
        calculate_price(
            offer.tons, 400, costs, offer.rate_eur_per_km_ton * 2
        ).payout_eur
        > base.payout_eur
    )
    context = offer.market_context
    changed = replace(
        offer,
        market_context=replace(
            context,
            cargo_value_eur_per_t=context.cargo_value_eur_per_t * 2,
            cargo_value_eur=round(
                offer.tons * context.cargo_value_eur_per_t * 2
            ),
        ),
    )
    assert (
        calculate_price(changed.tons, 400, costs, changed.rate_eur_per_km_ton)
        == base
    )
    assert (
        calculate_price(
            offer.tons,
            400,
            replace(costs, maintenance_cost_eur=400, total_cost_eur=480),
            offer.rate_eur_per_km_ton,
        ).operating_cost_eur
        > base.operating_cost_eur
    )


def test_historical_v2_and_missing_context_roundtrip_without_catalogue(
    synthetic_game,
):
    from dataclasses import asdict

    offer = synthetic_game.list_contracts()[0]
    historical = HistoricalContractSnapshot.from_offer(offer)
    assert load_historical_contract(asdict(historical)) == historical
    old = asdict(historical)
    old.pop("market_context")
    old["market_model"] = "nhm_v1"
    restored = load_historical_contract(old)
    assert restored.market_context is None
    assert restored.tons == offer.tons


async def test_dispatch_resolves_only_missing_exact_facility_snapshot(
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
    assert (
        synthetic_game.transport_dispatch.calculate_quote(
            offer, quote.dispatch_route, vehicle
        ).economics
        == quote.economics
    )
    model = next(
        m
        for m in synthetic_game_context.catalogue.list_models()
        if m.id == vehicle.model_id
    )
    unsupported = replace(
        model,
        transport_capabilities=tuple(
            replace(c, suitability_game=0)
            for c in model.transport_capabilities
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


def test_market_reads_and_refresh_never_call_providers_or_generate(
    synthetic_game,
):
    readiness = synthetic_game.market_services.routes.readiness
    with patch.object(
        readiness,
        "load",
        side_effect=AssertionError,
    ):
        retained = synthetic_game.list_contracts()
        assert synthetic_game.list_contracts() == retained
        regenerated = synthetic_game.refresh_contracts()
        assert regenerated == retained
        assert {o.origin.city.city_uid for o in regenerated} == {
            synthetic_game.get_vehicle("truck_01").location.city.city_uid
        }
