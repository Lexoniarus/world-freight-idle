"""Server-authoritative energy quotes, atomic settlement and public privacy."""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import project_dashboard, project_quote
from app.api.v1.traffic_projection import project_traffic
from app.domain.energy import EnergyProfile
from app.domain.errors import CatalogueError
from app.repositories.relational_traffic import SqliteTrafficReader
from tests.support.game import first_berlin_contract
from tests.support.game_clock import set_game_clock
from tests.support.market import seed_test_offers


def prepare_electric_vehicle(synthetic_game, synthetic_game_context):
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    model = next(
        m
        for m in synthetic_game_context.catalogue.list_models()
        if m.id == vehicle.model_id
    )
    vehicle.apply_model(
        replace(
            model, energy=EnergyProfile("electric", "kWh", 100, 20, 35, 0.1)
        )
    )
    vehicle.consume_energy(90)
    synthetic_game.state_repository.save_vehicle(vehicle)
    synthetic_game.time_scale = 100
    synthetic_game.transport_dispatch.time_scale = 100
    return vehicle


async def test_energy_quote_dispatch_pause_and_offline_settlement(
    synthetic_game, synthetic_game_context, database
):
    vehicle = prepare_electric_vehicle(
        synthetic_game,
        synthetic_game_context,
    )
    now = [synthetic_game.now()]
    set_game_clock(synthetic_game, lambda: now[0])
    contract = first_berlin_contract(synthetic_game)
    with pytest.raises(TypeError):
        await synthetic_game.quote_contract(contract["id"])
    quote = project_quote(
        await synthetic_game.quote_contract(contract["id"], vehicle.id)
    )
    assert quote["duration_seconds"] == 14400
    assert quote["driving_seconds"] == 160
    assert quote["pause_seconds"] == 21
    assert quote["total_duration_seconds"] == 181
    assert quote["energy_stop_count"] == 1
    assert quote["energy_consumption"] == 80
    trip = await synthetic_game.dispatch(contract["id"], vehicle.id)
    assert trip.journey.duration_seconds == 181
    assert trip.route.duration_seconds == 14400
    assert trip.operating_cost_eur == quote["operating_cost_eur"]
    now[0] += 10
    dashboard = project_dashboard(synthetic_game.dashboard())
    assert dashboard["vehicles"][0]["energy_level"] == 10
    assert dashboard["transports"][0]["progress"]["phase"] == "charging"
    assert dashboard["transports"][0]["progress"]["fraction"] == 0
    public = project_traffic(
        SqliteTrafficReader(database).list_active_transports(now[0]),
        "other-user",
    )
    assert public[0]["journey"]["segments"][0]["phase"] == "charging"
    assert not any(
        secret in json.dumps(public)
        for secret in (
            "energy_level",
            "start_energy",
            "end_energy",
            "payout_eur",
            "consumption_per_100km",
        )
    )
    now[0] = trip.departed_at + 21
    assert (
        project_dashboard(synthetic_game.dashboard())["vehicles"][0][
            "energy_level"
        ]
        == 100
    )
    assert synthetic_game.get_vehicle(vehicle.id).energy_level == 10
    now[0] = trip.arrives_at + 1
    before = synthetic_game.player_state().cash
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        assert synthetic_game.reconcile_arrival()
        assert not synthetic_game.reconcile_arrival()
    assert synthetic_game.get_vehicle(vehicle.id).energy_level == 20
    assert synthetic_game.player_state().cash == before + trip.payout_eur
    assert (
        synthetic_game.state_repository.list_transports()[0].status
        == "settled"
    )
    seed_test_offers(synthetic_game)
    next_offer = next(
        o
        for o in synthetic_game.list_contracts()
        if o.origin.facility_uid == trip.destination.facility_uid
        and o.tons <= vehicle.capacity_tons
    )
    next_trip = await synthetic_game.dispatch(next_offer.id, vehicle.id)
    assert next_trip.journey.segments[0].start_energy == 20
    assert next_trip.journey.segments[0].end_km == 50


async def test_dispatch_replans_after_routing_and_settlement_rolls_back(
    synthetic_game,
    synthetic_game_context,
):
    vehicle = prepare_electric_vehicle(
        synthetic_game,
        synthetic_game_context,
    )
    contract = first_berlin_contract(synthetic_game)
    readiness = synthetic_game.player_market.routes.readiness
    original_load = readiness.load
    changed = False

    def load_then_change_energy(*args):
        nonlocal changed
        route = original_load(*args)
        if not changed:
            changed = True
            current = synthetic_game.get_vehicle(vehicle.id)
            current.refill_energy()
            synthetic_game.state_repository.save_vehicle(current)
        return route

    with patch.object(readiness, "load", side_effect=load_then_change_energy):
        trip = await synthetic_game.dispatch(contract["id"], vehicle.id)
    assert trip.journey.stop_count == 0
    assert trip.journey.segments[0].start_energy == 100
    set_game_clock(synthetic_game, lambda: trip.arrives_at + 1)
    before = synthetic_game.player_state()
    with patch.object(
        synthetic_game.state_repository,
        "save_player",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError):
            synthetic_game.reconcile_arrival()
    assert synthetic_game.get_vehicle(vehicle.id).energy_level == 100
    assert synthetic_game.get_vehicle(vehicle.id).status == "enroute"
    assert synthetic_game.player_state() == before
    assert (
        synthetic_game.state_repository.list_transports()[0].status == "active"
    )
    corrupted = synthetic_game.get_vehicle(vehicle.id)
    # Simulate a damaged persisted departure checkpoint, not a legal mutation.
    corrupted._energy_level = 99
    synthetic_game.state_repository.save_vehicle(corrupted)
    with pytest.raises(ValueError, match="checkpoint"):
        synthetic_game.reconcile_arrival()
    assert synthetic_game.player_state() == before
    corrupted._energy_level = 100
    synthetic_game.state_repository.save_vehicle(corrupted)
    assert synthetic_game.reconcile_arrival()
    assert synthetic_game.get_vehicle(vehicle.id).energy_level == 20


async def test_quote_rejects_offer_changed_during_routing(synthetic_game):
    contract = first_berlin_contract(synthetic_game)
    readiness = synthetic_game.player_market.routes.readiness
    original_load = readiness.load
    changed = False

    def load_then_change_offer(*args):
        nonlocal changed
        route = original_load(*args)
        if not changed:
            changed = True
            offers = synthetic_game.state_repository.list_offers()
            synthetic_game.state_repository.replace_offers(
                tuple(
                    replace(
                        offer,
                        rate_eur_per_km_ton=(offer.rate_eur_per_km_ton + 0.01),
                    )
                    if offer.id == contract["id"]
                    else offer
                    for offer in offers
                )
            )
        return route

    with patch.object(readiness, "load", load_then_change_offer):
        with pytest.raises(ValueError, match="geändert"):
            await synthetic_game.quote_contract(contract["id"], "truck_01")
    assert synthetic_game.get_vehicle("truck_01").status == "idle"
    assert synthetic_game.state_repository.list_active_transports() == ()


async def test_dispatch_rejects_offer_changed_after_quote(synthetic_game):
    contract = first_berlin_contract(synthetic_game)
    quote = await synthetic_game.quote_contract(contract["id"], "truck_01")
    before = synthetic_game.player_state()
    synthetic_game.state_repository.replace_offers(
        tuple(
            replace(
                offer, rate_eur_per_km_ton=offer.rate_eur_per_km_ton + 0.01
            )
            if offer.id == contract["id"]
            else offer
            for offer in synthetic_game.state_repository.list_offers()
        )
    )
    with synthetic_game.unit_of_work.transaction():
        with pytest.raises(ValueError, match="geändert"):
            synthetic_game.transport_dispatch.commit_dispatch(
                contract["id"],
                "truck_01",
                quote,
            )
    assert synthetic_game.player_state() == before
    assert synthetic_game.get_vehicle("truck_01").status == "idle"
    assert synthetic_game.state_repository.list_active_transports() == ()
