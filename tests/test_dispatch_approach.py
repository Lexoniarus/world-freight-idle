"""Counterexamples for real pickup travel, checkpoints and saved routes."""

import asyncio
import json
from dataclasses import asdict, replace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.game_projection import project_quote, project_transport
from app.api.v1.traffic_projection import project_traffic
from app.domain.dispatch_journey import plan_dispatch_journey
from app.domain.economics import CostBreakdown
from app.domain.energy import EnergyProfile
from app.domain.errors import RoutingError
from app.domain.geography import City, Coordinates, Country
from app.domain.pricing import calculate_price
from app.domain.routes import DispatchRoutePlan, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot
from app.repositories.relational_traffic import SqliteTrafficReader
from app.repositories.transport_mapping import (
    load_dispatch_route,
    load_transport,
)
from tests.test_market_lifecycle import other_facility_offer


@pytest.fixture
def route_plan():
    city = City(
        "00000000-0000-0000-0000-000000000001",
        "City",
        Country("DE", "Germany"),
    )
    start = FacilityLocationSnapshot(
        "A",
        None,
        "A",
        "warehouse",
        city,
        "Street A",
        Coordinates(50, 10),
        "verified_coordinates",
        (),
        "4.2.0",
        (),
        "resolved",
        True,
    )
    pickup = replace(start, facility_uid="B", coordinates=Coordinates(50, 11))
    destination = replace(
        start, facility_uid="C", coordinates=Coordinates(50, 12)
    )
    return DispatchRoutePlan(
        start,
        pickup,
        destination,
        RouteSnapshot(((11, 50), (12, 50)), 100, 3600, "test"),
        RouteSnapshot(((10, 50), (11, 50)), 50, 7200, "test"),
    )


def test_dispatch_route_invariants_and_historical_mapping(route_plan):
    plan = route_plan
    assert plan.total_route.distance_km == 150
    assert plan.total_route.duration_seconds == 10800
    assert plan.total_route.coordinates == ((10, 50), (11, 50), (12, 50))
    assert [leg.purpose for leg in plan.legs] == ["approach", "delivery"]
    assert plan.legs[0].end_km == plan.legs[1].start_km == 50
    assert plan.legs[1].routing_duration_seconds == 3600
    assert load_dispatch_route(asdict(plan)) == plan
    assert load_dispatch_route(None) is None
    with pytest.raises(TypeError):
        load_dispatch_route({**asdict(plan), "unknown": True})
    with pytest.raises(KeyError):
        load_dispatch_route({**asdict(plan), "approach": {}})
    direct = replace(plan, start=plan.pickup, approach=None)
    assert direct.total_route == plan.delivery
    assert len(direct.legs) == 1
    assert load_dispatch_route(asdict(direct)) == direct
    colocated = replace(plan.start, coordinates=plan.pickup.coordinates)
    with pytest.raises(ValueError, match="approach"):
        replace(direct, start=colocated)
    with pytest.raises(ValueError, match="approach"):
        replace(plan, approach=None)
    without_start_display = replace(
        plan,
        start=replace(plan.start, coordinates=None),
    )
    assert without_start_display.start.coordinates is None
    without_destination_display = replace(
        plan,
        destination=replace(plan.destination, coordinates=None),
    )
    assert without_destination_display.destination.coordinates is None
    other_city = replace(
        plan.start.city,
        city_uid="00000000-0000-0000-0000-000000000002",
    )
    with pytest.raises(ValueError, match="Abholstadt"):
        replace(plan, start=replace(plan.start, city=other_city))
    snapped = replace(
        plan.delivery,
        coordinates=((11.001, 50), (12, 50)),
    )
    assert len(replace(plan, delivery=snapped).total_route.coordinates) == 4


def test_dispatch_journey_preserves_leg_speeds_energy_and_boundary(route_plan):
    energy = EnergyProfile("diesel", "l", 100, 20, 10, 0.1)
    # Approach provider speed 25 km/h; delivery limited to 50 km/h.
    plan = plan_dispatch_journey(route_plan, 50, energy, 25, 1)
    assert plan.segments[0].ends_at == 7200
    assert plan.progress_at(7200).distance_km == 50
    assert plan.progress_at(7200).energy_level == 15
    assert plan.progress_at(9000).phase == "refuelling"
    assert plan.progress_at(9000).distance_km == 75
    assert plan.duration_seconds == 15000
    assert plan.progress_at(15000).energy_level == 85
    # A stop during approach carries its new level into delivery.
    low = plan_dispatch_journey(route_plan, 50, energy, 15, 1)
    assert low.progress_at(3600).phase == "refuelling"
    assert low.progress_at(7800).distance_km == 50
    assert low.progress_at(7800).energy_level == 95
    # Exactly exhausted reserve at B: a stop at B, no gap or extra loading.
    exact = plan_dispatch_journey(route_plan, 50, energy, 20, 1)
    assert exact.progress_at(7200).phase == "refuelling"
    assert exact.progress_at(7200).distance_km == 50
    assert exact.progress_at(7800).phase == "driving"
    assert exact.progress_at(7800).energy_level == 100
    for left, right in zip(exact.segments, exact.segments[1:]):
        assert left.ends_at == right.starts_at
        assert left.end_km == right.start_km
        assert left.end_energy == right.start_energy
    direct = replace(route_plan, start=route_plan.pickup, approach=None)
    assert plan_dispatch_journey(direct, 50, energy, 100, 1).distance_km == 100


def test_approach_costs_do_not_pay_freight_or_duplicate_base():
    costs = CostBreakdown("test", 2, "diesel", "l", 1.5, 80, 300, (), 0, 380)
    quote = calculate_price(10, 100, costs, 0.1)
    direct = calculate_price(
        10,
        100,
        replace(costs, maintenance_cost_eur=200, total_cost_eur=280),
        0.1,
    )
    assert quote.payout_eur == direct.payout_eur == 320
    assert quote.operating_cost_eur == 380
    assert quote.profit_eur == -60


async def test_planner_routes_from_checkpoint_by_facility_identity(game):
    offer = other_facility_offer(game)
    start = game.get_vehicle("truck_01").location
    assert start is not None
    router = game.router

    with patch.object(router, "route", wraps=router.route) as routed:
        plan = await game.dispatch_planning.route(start, offer)
        assert routed.await_count == 2
        assert plan.start == start
        assert plan.approach is not None

    with patch.object(router, "route", wraps=router.route) as routed:
        direct = await game.dispatch_planning.route(offer.origin, offer)
        assert routed.await_count == 1
        assert direct.approach is None

    colocated_display = replace(
        start,
        coordinates=offer.origin.coordinates,
    )
    with patch.object(router, "route", wraps=router.route) as routed:
        plan = await game.dispatch_planning.route(colocated_display, offer)
        assert routed.await_count == 2
        assert plan.approach is not None

    missing_start_display = replace(start, coordinates=None)
    with patch.object(router, "route", wraps=router.route) as routed:
        plan = await game.dispatch_planning.route(missing_start_display, offer)
        assert routed.await_count == 2
        assert plan.start.coordinates is None
        assert plan.approach is not None

    missing_destination_display = replace(
        offer,
        destination=replace(offer.destination, coordinates=None),
    )
    with patch.object(router, "route", wraps=router.route) as routed:
        plan = await game.dispatch_planning.route(
            start,
            missing_destination_display,
        )
        assert routed.await_count == 2
        assert plan.destination.coordinates is None


async def test_approach_dispatch_reload_public_privacy_and_offline_arrival(
    game, database
):
    offer = other_facility_offer(game)
    start = game.get_vehicle("truck_01").location
    original_route = game.router.route

    async def unlocked_route(*args):
        # A second connection can acquire the writer while routing awaits.
        with database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        return await original_route(*args)

    with patch.object(game.router, "route", side_effect=unlocked_route):
        quote = await game.quote_contract(offer.id, "truck_01")
        trip = await game.dispatch(offer.id, "truck_01")
    projected = project_quote(quote)
    assert projected["start"]["facility_uid"] == start.facility_uid
    assert projected["approach_distance_km"] == 400
    assert projected["delivery_distance_km"] == 400
    assert projected["distance_km"] == 800
    assert quote.economics == calculate_price(
        offer.tons,
        400,
        quote.economics.cost_breakdown,
        offer.rate_eur_per_km_ton,
        minimum_eur_per_km=offer.market_context.tariff.minimum_eur_per_km,
    )
    restored = game.state_repository.list_active_transports()[0]
    assert restored == trip
    assert restored.dispatch_route.start == start
    assert game.get_vehicle("truck_01").location == start
    boundary = next(
        s.ends_at for s in trip.journey.segments if s.end_km == 400
    )
    for elapsed, leg_distance in (
        (boundary / 2, 200),
        (boundary, 400),
        (boundary + 1, 400),
    ):
        now = trip.departed_at + elapsed
        game.now = lambda: now
        assert not game.reconcile_arrival()
        assert (
            game.get_transport(trip.id).progress_at(now).distance_km
            >= leg_distance
        )
    public = project_traffic(
        SqliteTrafficReader(database).list_active_transports(now), "other"
    )[0]
    assert public["route_legs"] == projected["route_legs"]
    assert not any(
        secret in json.dumps(public)
        for secret in (
            "payout_eur",
            "operating_cost",
            "start_energy",
            "end_energy",
            "energy_level",
        )
    )
    with pytest.raises(ValueError, match="Dispatch route"):
        replace(
            trip,
            dispatch_route=replace(
                trip.dispatch_route,
                delivery=replace(
                    trip.dispatch_route.delivery, distance_km=401
                ),
            ),
        )
    # Existing snapshots without the optional addition remain untouched.
    old = asdict(trip)
    old.pop("dispatch_route")
    historical = load_transport(old)
    assert historical.route == trip.route
    assert historical.payout_eur == trip.payout_eur
    assert historical.dispatch_route is None
    assert project_transport(historical)["approach_distance_km"] == 0
    assert project_transport(historical)["route_legs"] == []
    cash = game._get_player().cash
    game.now = lambda: trip.arrives_at + 1
    assert game.reconcile_arrival()
    assert not game.reconcile_arrival()
    assert game.get_vehicle("truck_01").location == trip.destination
    assert game._get_player().cash == cash + trip.payout_eur


async def test_changed_departure_and_provider_failure_never_dispatch(game):
    offer = other_facility_offer(game)
    vehicle = game.get_vehicle("truck_01")
    cash = game._get_player().cash
    route = game.router.route

    async def changed_location(*args):
        result = await route(*args)
        current = game.get_vehicle(vehicle.id)
        current.reposition_within_city(offer.origin)
        game.state_repository.save_vehicle(current)
        return result

    with patch.object(game.router, "route", side_effect=changed_location):
        with pytest.raises(ValueError, match="Fahrzeugstandort"):
            await game.dispatch(offer.id, vehicle.id)
    assert game._get_player().cash == cash
    assert not game.state_repository.list_active_transports()

    # The departure must be checked again inside the committing transaction.
    game.state_repository.save_vehicle(vehicle)
    quote = await game.quote_contract(offer.id, vehicle.id)
    current = game.get_vehicle(vehicle.id)
    current.reposition_within_city(offer.origin)
    game.state_repository.save_vehicle(current)
    with patch.object(game, "quote_contract", AsyncMock(return_value=quote)):
        with pytest.raises(ValueError, match="Fahrzeugstandort"):
            await game.dispatch(offer.id, vehicle.id)
    game.state_repository.save_vehicle(vehicle)
    with patch.object(
        game.router, "route", side_effect=RoutingError("offline")
    ):
        with pytest.raises(RoutingError):
            await game.dispatch(offer.id, vehicle.id)
    with patch.object(
        game,
        "quote_contract",
        AsyncMock(return_value=replace(quote, dispatch_route=None)),
    ):
        with pytest.raises(ValueError, match="departure plan"):
            await game.dispatch(offer.id, vehicle.id)
    assert game.get_vehicle(vehicle.id).location == vehicle.location
    assert game.get_vehicle(vehicle.id).status == "idle"
    assert game._get_player().cash == cash
    assert game.get_contract(offer.id) == offer
    assert not game.state_repository.list_active_transports()


async def test_concurrent_approaches_reserve_and_charge_only_once(game):
    offer = other_facility_offer(game)
    before = game.get_vehicle("truck_01")
    cash = game._get_player().cash
    original = game.router.route
    barrier = asyncio.Event()
    calls = 0

    async def overlapping_routes(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            barrier.set()
        await barrier.wait()
        return await original(*args)

    with patch.object(game.router, "route", side_effect=overlapping_routes):
        results = await asyncio.gather(
            game.dispatch(offer.id, before.id),
            game.dispatch(offer.id, before.id),
            return_exceptions=True,
        )
    assert sum(isinstance(result, KeyError) for result in results) == 1
    saved = game.state_repository.list_active_transports()
    assert len(saved) == 1
    assert game._get_player().cash == cash - saved[0].operating_cost_eur
    assert game.get_vehicle(before.id).location == before.location
    assert game.get_vehicle(before.id).status == "enroute"


@pytest.mark.parametrize("failure", ["remove_offer", "replace_offers"])
async def test_approach_pruning_failure_rolls_back_complete_dispatch(
    game, failure
):
    offer = other_facility_offer(game)
    before = game.get_vehicle("truck_01")
    cash = game._get_player().cash
    offers = game.state_repository.list_offers()
    with patch.object(
        game.state_repository,
        failure,
        side_effect=RuntimeError("write failed"),
    ):
        with pytest.raises(RuntimeError, match="write failed"):
            await game.dispatch(offer.id, before.id)
    assert game._get_player().cash == cash
    assert game.get_vehicle(before.id).status == "idle"
    assert game.get_vehicle(before.id).location == before.location
    assert game.state_repository.list_offers() == offers
    assert not game.state_repository.list_active_transports()
