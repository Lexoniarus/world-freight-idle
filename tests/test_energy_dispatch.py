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
from tests.test_game import first_berlin_contract


def prepare_electric_vehicle(game):
    vehicle = game.state_repository.list_vehicles()[0]
    model = next(
        m for m in game.catalogue.list_models() if m.id == vehicle.model_id
    )
    vehicle.apply_model(
        replace(
            model, energy=EnergyProfile("electric", "kWh", 100, 20, 35, 0.1)
        )
    )
    vehicle.consume_energy(90)
    game.state_repository.save_vehicle(vehicle)
    game.time_scale = 100
    return vehicle


async def test_energy_quote_dispatch_pause_and_offline_settlement(
    game, database
):
    vehicle = prepare_electric_vehicle(game)
    now = [game.now()]
    game.now = lambda: now[0]
    contract = first_berlin_contract(game)
    with pytest.raises(TypeError):
        await game.quote_contract(contract["id"])
    quote = project_quote(
        await game.quote_contract(contract["id"], vehicle.id)
    )
    assert quote["duration_seconds"] == 14400
    assert quote["driving_seconds"] == 160
    assert quote["pause_seconds"] == 21
    assert quote["total_duration_seconds"] == 181
    assert quote["energy_stop_count"] == 1
    assert quote["energy_consumption"] == 80
    trip = await game.dispatch(contract["id"], vehicle.id)
    assert trip.journey.duration_seconds == 181
    assert trip.route.duration_seconds == 14400
    assert trip.operating_cost_eur == quote["operating_cost_eur"]
    now[0] += 10
    dashboard = project_dashboard(game.dashboard())
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
        project_dashboard(game.dashboard())["vehicles"][0]["energy_level"]
        == 100
    )
    assert game.get_vehicle(vehicle.id).energy_level == 10
    now[0] = trip.arrives_at + 1
    before = game._get_player().cash
    with patch.object(
        game.catalogue, "list_models", side_effect=CatalogueError("offline")
    ):
        assert game.reconcile_arrival()
        assert not game.reconcile_arrival()
    assert game.get_vehicle(vehicle.id).energy_level == 20
    assert game._get_player().cash == before + trip.payout_eur
    assert game.state_repository.list_transports()[0].status == "settled"
    next_offer = next(
        o
        for o in game.refresh_market()
        if o.origin.facility_uid == trip.destination.facility_uid
        and o.tons <= vehicle.capacity_tons
    )
    next_trip = await game.dispatch(next_offer.id, vehicle.id)
    assert next_trip.journey.segments[0].start_energy == 20
    assert next_trip.journey.segments[0].end_km == 50


async def test_dispatch_replans_after_routing_and_settlement_rolls_back(game):
    vehicle = prepare_electric_vehicle(game)
    contract = first_berlin_contract(game)
    original_route = game.router.route

    async def route_then_change_energy(*args):
        route = await original_route(*args)
        current = game.get_vehicle(vehicle.id)
        current.refill_energy()
        game.state_repository.save_vehicle(current)
        return route

    with patch.object(
        game.router, "route", side_effect=route_then_change_energy
    ):
        trip = await game.dispatch(contract["id"], vehicle.id)
    assert trip.journey.stop_count == 0
    assert trip.journey.segments[0].start_energy == 100
    game.now = lambda: trip.arrives_at + 1
    before = game._get_player()
    with patch.object(
        game.state_repository,
        "save_player",
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError):
            game.reconcile_arrival()
    assert game.get_vehicle(vehicle.id).energy_level == 100
    assert game.get_vehicle(vehicle.id).status == "enroute"
    assert game._get_player() == before
    assert game.state_repository.list_transports()[0].status == "active"
    corrupted = game.get_vehicle(vehicle.id)
    # Simulate a damaged persisted departure checkpoint, not a legal mutation.
    corrupted._energy_level = 99
    game.state_repository.save_vehicle(corrupted)
    with pytest.raises(ValueError, match="checkpoint"):
        game.reconcile_arrival()
    assert game._get_player() == before
    corrupted._energy_level = 100
    game.state_repository.save_vehicle(corrupted)
    assert game.reconcile_arrival()
    assert game.get_vehicle(vehicle.id).energy_level == 20


async def test_quote_rejects_offer_changed_during_routing(game):
    contract = first_berlin_contract(game)
    original_route = game.router.route

    async def route_then_change_offer(*args):
        route = await original_route(*args)
        offers = game.state_repository.list_offers()
        game.state_repository.replace_offers(
            tuple(
                replace(o, rate_eur_per_km_ton=o.rate_eur_per_km_ton + 0.01)
                if o.id == contract["id"]
                else o
                for o in offers
            )
        )
        return route

    with patch.object(game.router, "route", route_then_change_offer):
        with pytest.raises(ValueError, match="geändert"):
            await game.quote_contract(contract["id"], "truck_01")
    assert game.get_vehicle("truck_01").status == "idle"
    assert game.state_repository.list_active_transports() == ()


async def test_dispatch_rejects_offer_changed_after_quote(game):
    contract = first_berlin_contract(game)
    quote = await game.quote_contract(contract["id"], "truck_01")
    before = game._get_player()
    game.state_repository.replace_offers(
        tuple(
            replace(
                offer, rate_eur_per_km_ton=offer.rate_eur_per_km_ton + 0.01
            )
            if offer.id == contract["id"]
            else offer
            for offer in game.state_repository.list_offers()
        )
    )
    with game.unit_of_work.transaction():
        with pytest.raises(ValueError, match="geändert"):
            game._commit_dispatch(contract["id"], "truck_01", quote)
    assert game._get_player() == before
    assert game.get_vehicle("truck_01").status == "idle"
    assert game.state_repository.list_active_transports() == ()
