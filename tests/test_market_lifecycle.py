"""Market v2 dispatch atomicity, refill isolation and history regression."""

import sqlite3
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.errors import CatalogueError
from app.domain.pricing import calculate_price
from app.repositories.snapshot_mapping import load_historical_contract
from app.services.fleet import build_owned_vehicle


def other_facility_offer(game):
    vehicle = game.get_vehicle("truck_01")
    return next(
        o
        for o in game.list_contracts()
        if o.origin.facility_uid != vehicle.facility_uid
    )


async def test_same_city_dispatch_repositions_and_prunes_atomically(game):
    offer = other_facility_offer(game)
    before = game.get_vehicle("truck_01")
    quote = await game.quote_contract(offer.id, before.id)
    trip = await game.dispatch(offer.id, before.id)
    vehicle = game.get_vehicle(before.id)
    assert vehicle.facility_uid == offer.origin.facility_uid
    assert vehicle.location == offer.origin == trip.origin
    assert vehicle.status == "enroute"
    assert trip.journey == quote.journey
    assert trip.operating_cost_eur == quote.economics.operating_cost_eur
    assert vehicle.energy_level == before.energy_level
    assert game.state_repository.list_offers() == ()


async def test_dispatch_failure_rolls_back_reposition_and_market(game):
    offer = other_facility_offer(game)
    before_vehicle = game.get_vehicle("truck_01")
    before_cash = game._get_player().cash
    before_offers = game.state_repository.list_offers()
    with patch.object(
        game.state_repository,
        "save_transport",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            await game.dispatch(offer.id, "truck_01")
    assert game.get_vehicle("truck_01").location == before_vehicle.location
    assert game.get_vehicle("truck_01").status == "idle"
    assert game._get_player().cash == before_cash
    assert game.state_repository.list_offers() == before_offers
    assert game.state_repository.list_active_transports() == ()


async def test_refill_failure_cannot_undo_committed_dispatch(game, caplog):
    caplog.set_level("ERROR", logger="app.services.market_lifecycle")
    offer = other_facility_offer(game)
    cash = game._get_player().cash
    with patch.object(
        type(game.market),
        "generate",
        side_effect=CatalogueError("refill offline"),
    ):
        trip = await game.dispatch(offer.id, "truck_01")
    assert game.get_vehicle("truck_01").status == "enroute"
    assert game.get_vehicle("truck_01").location == offer.origin
    assert game._get_player().cash == cash - trip.operating_cost_eur
    assert game.state_repository.list_active_transports() == (trip,)
    assert not game.state_repository.list_offers()
    assert any(
        getattr(record, "event", "") == "market.refill_failed"
        for record in caplog.records
    )
    game.refresh_market()
    assert game.state_repository.list_active_transports() == (trip,)
    assert game._get_player().cash == cash - trip.operating_cost_eur


async def test_refill_uses_separate_transaction_and_rolls_back_only_new_offers(
    game,
    database,
):
    offer = other_facility_offer(game)
    first = game.get_vehicle("truck_01")
    model = next(
        m for m in game.catalogue.list_models() if m.id == first.model_id
    )
    second = build_owned_vehicle(model, "second", first.location)
    game.state_repository.save_vehicle(second)
    original_generate = game.market.generate
    original_replace = game.state_repository.replace_offers
    refill_started = False

    def generate(*args, **kwargs):
        nonlocal refill_started
        # A separate SQLite connection cannot observe uncommitted writes.
        with sqlite3.connect(database.path) as connection:
            assert (
                connection.execute(
                    "SELECT status FROM owned_vehicles WHERE vehicle_id=?",
                    (first.id,),
                ).fetchone()[0]
                == "enroute"
            )
        assert game.state_repository.list_active_transports()
        assert game.get_vehicle(first.id).status == "enroute"
        refill_started = True
        return original_generate(*args, **kwargs)

    def replace_offers(offers):
        original_replace(offers)
        if refill_started:
            raise RuntimeError("refill write failed")

    with (
        patch.object(type(game.market), "generate", side_effect=generate),
        patch.object(
            game.state_repository, "replace_offers", side_effect=replace_offers
        ),
    ):
        trip = await game.dispatch(offer.id, first.id)
    assert refill_started
    assert game.state_repository.list_active_transports() == (trip,)
    remaining = game.state_repository.list_offers()
    assert offer.id not in {o.id for o in remaining}
    assert remaining
    refilled = game.refresh_market()
    assert len(refilled) >= len(remaining)
    assert all(
        o.origin.city.city_uid == first.location.city.city_uid
        for o in refilled
    )


async def test_arrival_activates_city_and_preserves_historical_terms(
    game, monkeypatch
):
    offer = next(
        o
        for o in game.list_contracts()
        if o.destination.city.city_uid != o.origin.city.city_uid
    )
    build_trip = game._build_trip

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

    with patch.object(game, "_build_trip", side_effect=historical_trip):
        historical = await game.dispatch(offer.id, "truck_01")
    trip = historical
    monkeypatch.setattr(game, "now", lambda: trip.arrives_at + 1)
    with patch.object(
        game.catalogue, "list_models", side_effect=CatalogueError("offline")
    ):
        assert game.reconcile_arrival()
        assert not game.reconcile_arrival()
    settled = game.state_repository.list_transports()[0]
    assert settled.contract == historical.contract
    assert settled.payout_eur == trip.payout_eur
    assert game.get_vehicle("truck_01").location == trip.destination
    offers = game.refresh_market()
    assert offers
    assert {o.origin.city.city_uid for o in offers} == {
        trip.destination.city.city_uid
    }
    assert {o.id for o in game.refresh_market()} == {o.id for o in offers}


def test_retention_prunes_v1_unavailable_fleet_and_expiring_offers(game):
    offers = game.list_contracts()
    first = offers[0]
    legacy = replace(
        first, id="legacy", market_model="nhm_v1", market_context=None
    )
    expired = replace(first, id="expiring", expires_at=game.now() + 30)
    game.state_repository.replace_offers((*offers, legacy, expired))
    assert game.refresh_market() == offers
    assert game.contract_choices(offers)[0].eligible_vehicle_ids == (
        "truck_01",
    )
    vehicle = game.get_vehicle("truck_01")
    vehicle._capacity_tons = 0.1
    game.state_repository.save_vehicle(vehicle)
    new = game.refresh_market()
    assert new
    assert not ({o.id for o in offers} & {o.id for o in new})
    assert all(o.tons <= 0.1 for o in new)
    with patch.object(
        game.catalogue, "list_models", side_effect=CatalogueError("offline")
    ):
        with pytest.raises(CatalogueError):
            game.refresh_market()
    assert game.state_repository.list_offers() == tuple(new)


def test_reposition_rejects_busy_other_city_and_missing_location(game):
    vehicle = game.get_vehicle("truck_01")
    offer = next(
        o
        for o in game.list_contracts()
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


def test_freight_rate_changes_payout_but_cargo_value_does_not(game):
    offer = game.list_contracts()[0]
    base = calculate_price(offer.tons, 400, 0.5, offer.rate_eur_per_km_ton)
    assert (
        calculate_price(
            offer.tons, 800, 0.5, offer.rate_eur_per_km_ton
        ).payout_eur
        > base.payout_eur
    )
    assert (
        calculate_price(
            offer.tons * 2, 400, 0.5, offer.rate_eur_per_km_ton
        ).payout_eur
        > base.payout_eur
    )
    assert (
        calculate_price(
            offer.tons, 400, 0.5, offer.rate_eur_per_km_ton * 2
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
        calculate_price(changed.tons, 400, 0.5, changed.rate_eur_per_km_ton)
        == base
    )
    assert (
        calculate_price(
            offer.tons, 400, 1, offer.rate_eur_per_km_ton
        ).operating_cost_eur
        > base.operating_cost_eur
    )


def test_historical_v2_and_missing_context_roundtrip_without_catalogue(game):
    from dataclasses import asdict

    offer = game.list_contracts()[0]
    historical = HistoricalContractSnapshot.from_offer(offer)
    assert load_historical_contract(asdict(historical)) == historical
    old = asdict(historical)
    old.pop("market_context")
    old["market_model"] = "nhm_v1"
    restored = load_historical_contract(old)
    assert restored.market_context is None
    assert restored.tons == offer.tons


async def test_dispatch_resolves_only_missing_exact_facility_snapshot(game):
    offer = other_facility_offer(game)
    vehicle = game.get_vehicle("truck_01")
    location = vehicle.location
    assert location is not None
    with pytest.raises(ValueError, match="stored facility"):
        vehicle.restore_location(offer.origin)
    changed = replace(location, label="Changed reference name")
    with pytest.raises(ValueError, match="existing location"):
        vehicle.restore_location(changed)
    vehicle.restore_location(location)
    vehicle._location = None
    game.state_repository.save_vehicle(vehicle)
    await game.quote_contract(offer.id, vehicle.id)
    assert game.get_vehicle(vehicle.id).location is None
    trip = await game.dispatch(offer.id, vehicle.id)
    assert game.get_vehicle(vehicle.id).location == trip.origin
