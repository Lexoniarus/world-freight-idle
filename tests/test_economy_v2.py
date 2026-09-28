"""Stored tariff and purchase-cost regressions for the new economy."""

from dataclasses import asdict, replace
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.bootstrap import build_market_startup, build_preferences
from app.domain.analytics_labels import vehicle_labels
from app.domain.company_colors import COMPANY_COLORS, player_color
from app.domain.economics import (
    EnergyPurchase,
    VehicleCostProfile,
    journey_costs,
    whole_euros,
)
from app.domain.energy import EnergyKind, EnergyProfile, EnergyUnit
from app.domain.journeys import plan_journey, unmetered_journey
from app.domain.tariffs import FreightTariff, freight_tariff
from app.repositories.transport_mapping import load_cost_breakdown
from app.services.cost_profiles import VehicleCostResolver


def metered(kind: EnergyKind = "diesel", level=100, distance=1000):
    units: dict[EnergyKind, EnergyUnit] = {
        "diesel": "l",
        "gas": "kg",
        "electric": "kWh",
    }
    energy = EnergyProfile(
        kind,
        units[kind],
        100,
        20,
        10,
        0.1,
    )
    return plan_journey(distance, distance * 60, 100, energy, level, 1)


@pytest.mark.parametrize(
    "kind,price", [("diesel", 1.5), ("gas", 1.2), ("electric", 0.3)]
)
@pytest.mark.parametrize(
    "level,distance", [(100, 10), (50, 1000), (10, 1600), (100, 500)]
)
def test_purchase_costs_charge_only_planned_energy_and_reconcile(
    kind, price, level, distance
):
    journey = metered(kind, level, distance)
    costs = journey_costs(journey, VehicleCostProfile(0.08))
    assert costs.maintenance_cost_eur == whole_euros(
        Decimal(str(distance)) * Decimal("0.08")
    )
    for purchase in costs.purchases:
        segment = journey.segments[purchase.segment_index]
        assert (
            segment.end_energy is not None and segment.start_energy is not None
        )
        assert purchase.quantity == pytest.approx(
            segment.end_energy - segment.start_energy
        )
        assert purchase.cost_eur == whole_euros(
            Decimal(str(purchase.quantity)) * Decimal(str(price))
        )
    assert costs.energy_cost_eur == sum(p.cost_eur for p in costs.purchases)
    assert (
        costs.total_cost_eur
        == 80 + costs.maintenance_cost_eur + costs.energy_cost_eur
    )
    assert load_cost_breakdown(asdict(costs)) == costs
    if distance == 10:
        assert not costs.purchases and costs.energy_cost_eur == 0
    assert whole_euros(Decimal("2.5")) == 3


def test_cost_values_reject_invalid_or_inconsistent_components():
    costs = journey_costs(metered(), VehicleCostProfile(0.08))
    for changes in [
        dict(policy_version=""),
        dict(energy_unit="kg"),
        dict(energy_price_eur_per_unit=0),
        dict(total_cost_eur=0),
        dict(energy_cost_eur=0),
        dict(purchases=[]),
        dict(maintenance_eur_per_km=float("nan")),
        dict(base_cost_eur=-1),
    ]:
        with pytest.raises(ValueError):
            replace(costs, **changes)
    for args in [(-1, 1, 1), (0, 0, 1), (0, 1, -1)]:
        with pytest.raises(ValueError):
            EnergyPurchase(*args)
    with pytest.raises(ValueError):
        journey_costs(unmetered_journey(10, 60), VehicleCostProfile(0.08))
    assert load_cost_breakdown(None) is None


def test_tariff_uses_concrete_nhm_and_explicit_maintenance(
    catalogue, world_catalogue
):
    models = catalogue.list_models()
    assert len(models) == 14
    resolver = VehicleCostResolver(catalogue)
    for model in models:
        costs = resolver.resolve(model.id)
        assert (
            costs.maintenance_eur_per_km
            == model.maintenance_eur_per_1000_km / 1000
        )
        tariff = freight_tariff(costs, model.energy, 0.65, 0.65)
        expected = freight_tariff(costs, model.energy, 0.65, 0.65)
        assert tariff == expected
        assert freight_tariff(
            costs, model.energy, 1.3, 0.65
        ).minimum_eur_per_km == pytest.approx(2 * tariff.minimum_eur_per_km)
        with pytest.raises(ValueError):
            replace(model, maintenance_eur_per_1000_km=None)
    for model_id in [None, "missing"]:
        with pytest.raises(ValueError):
            resolver.resolve(model_id)
    energy = models[0].energy
    for factor, reference in [(0, 1), (1, 0)]:
        with pytest.raises(ValueError):
            freight_tariff(VehicleCostProfile(0.08), energy, factor, reference)
    for values in [("", 1, 1, 1, 1), ("v1", 0, 1, 1, 1)]:
        with pytest.raises(ValueError):
            FreightTariff(*values)


async def test_dispatch_stores_costs_and_preserves_tariff_for_vehicle_choice(
    game,
):
    offer = game.list_contracts()[0]
    vehicle = game.get_vehicle("truck_01")
    quote = await game.quote_contract(offer.id, vehicle.id)
    tariff = offer.market_context.tariff
    with patch.object(
        VehicleCostResolver,
        "resolve",
        return_value=VehicleCostProfile(2),
    ):
        expensive = await game.quote_contract(offer.id, vehicle.id)
    assert expensive.economics.payout_eur == quote.economics.payout_eur
    assert (
        expensive.economics.operating_cost_eur
        > quote.economics.operating_cost_eur
    )
    assert game.get_contract(offer.id).market_context.tariff == tariff
    trip = await game.dispatch(offer.id, vehicle.id)
    saved = game.state_repository.list_transports()[0]
    assert (
        saved.cost_breakdown
        == quote.economics.cost_breakdown
        == trip.cost_breakdown
    )
    with pytest.raises(ValueError):
        replace(trip, operating_cost_eur=0)
    route = quote.dispatch_route
    assert route is not None
    with pytest.raises(ValueError, match="Tarif"):
        game.dispatch_planning.quote(
            replace(
                offer,
                market_context=replace(offer.market_context, tariff=None),
            ),
            route,
            vehicle,
            1,
        )


def test_startup_rebuild_is_global_atomic_and_does_not_route(
    runtime, game, database
):
    startup = build_market_startup(runtime)
    original = game.state_repository.list_offers()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('z-owner', 'Second', 'hash', 0)"
        )
        connection.execute(
            "INSERT INTO player_states VALUES ('z-owner', 1000, 0, 0)"
        )
    real_factory = startup.lifecycle

    def fail_second(owner):
        if owner == "z-owner":
            raise ValueError("second owner failure")
        return real_factory(owner)

    with patch.object(startup, "lifecycle", side_effect=fail_second):
        with pytest.raises(ValueError, match="second owner"):
            startup.rebuild()
    assert game.state_repository.list_offers() == original
    with patch.object(
        runtime.router, "route", side_effect=AssertionError("No routing")
    ):
        startup.rebuild()
    assert game.state_repository.list_offers() != original
    assert not real_factory("z-owner").unit_of_work.repository.list_vehicles()
    assert not real_factory("z-owner").unit_of_work.repository.list_offers()


def test_preferences_are_account_scoped_persistent_and_palette_validated(
    runtime, database
):
    service = build_preferences(runtime)
    assert len(COMPANY_COLORS) == 10
    assert service.read("test-owner").company_color == player_color(
        "test-owner"
    )
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES ('second', 'Second', 'hash', 0)"
        )
    assert (
        service.update("test-owner", COMPANY_COLORS[0]).company_color
        == COMPANY_COLORS[0]
    )
    assert (
        build_preferences(runtime).read("test-owner").company_color
        == COMPANY_COLORS[0]
    )
    assert service.read("second").company_color == player_color("second")
    with pytest.raises(ValueError):
        service.update("test-owner", "red")
    assert service.read("test-owner").company_color == COMPANY_COLORS[0]


def test_analytics_labels_keep_identity_and_disambiguate_current_names():
    labels = vehicle_labels(
        (("first-1234", "Van"), ("other-1234", "Van"), ("truck", "Truck")),
        ("first-1234", "other-1234", "gone-1234", "truck"),
    )
    assert labels == {
        "first-1234": "Van · first-12",
        "other-1234": "Van · other-12",
        "gone-1234": "Fahrzeug gone-123",
        "truck": "Truck",
    }


def test_economy_audit_uses_actual_distribution_and_separates_cashflow(
    catalogue, world_catalogue
):
    from app.domain.economy_audit import audit_economy_case
    from app.domain.market import MarketVehicle
    from app.domain.market_calculations import biased_load_factor
    from app.domain.market_compatibility import vehicle_suitability
    from app.domain.market_profiles import vehicle_scale_for_segment

    profiles = world_catalogue.read().market_profiles
    reference = min(p.freight_rate_factor_game for p in profiles)
    covered = set()
    for model in catalogue.list_models():
        vehicle = MarketVehicle(
            "audit",
            model.id,
            "city",
            "truck",
            model.capacity_tons,
            vehicle_scale_for_segment(model.segment),
            model.transport_capabilities,
            VehicleCostProfile(model.maintenance_eur_per_1000_km / 1000),
            model.energy,
        )
        covered.add(vehicle.scale)
        profile = next(
            p for p in profiles if vehicle_suitability(vehicle, p) > 0
        )
        for load, distance in zip(profile.distance_profiles, (75, 375, 1000)):
            for draw in (0, 0.5, 1):
                result = audit_economy_case(
                    vehicle, profile, load, reference, draw, distance
                )
                assert result.load_factor == biased_load_factor(
                    load.load_factor_min, load.load_factor_max, draw
                )
                assert 0 < result.tons <= model.capacity_tons
                assert result.reference_margin >= 0.20
                assert (
                    result.booked_profit_eur
                    == result.payout_eur - result.booked_cost_eur
                )
    assert len(covered) == 4


def test_analytics_labels_expand_colliding_short_identities():
    labels = vehicle_labels(
        (("same0000-a", "Truck"), ("same0000-b", "Truck")),
        ("same0000-a", "same0000-b"),
    )
    assert len(set(labels.values())) == 2
    assert labels["same0000-a"] == "Truck · same0000-a"


async def test_vehicle_switch_preserves_offer_and_checks_actual_capacity(game):
    offer = game.list_contracts()[0]
    vehicle = game.get_vehicle("truck_01")
    original = offer
    quote = await game.quote_contract(offer.id, vehicle.id)
    vehicle._capacity_tons = offer.tons + 1
    game.state_repository.save_vehicle(vehicle)
    larger = await game.quote_contract(offer.id, vehicle.id)
    assert larger.economics.payout_eur == quote.economics.payout_eur
    assert game.get_contract(offer.id) == original
    vehicle._capacity_tons = offer.tons / 2
    game.state_repository.save_vehicle(vehicle)
    with pytest.raises(ValueError, match="Kapazität|kapazität"):
        await game.quote_contract(offer.id, vehicle.id)
    vehicle._capacity_tons = original.tons + 1
    with patch.object(
        type(game.market.candidates), "eligible_ids", return_value=()
    ):
        with pytest.raises(ValueError, match="Transportklasse"):
            game._validate_dispatch(vehicle, offer)


def test_vehicle_reference_cache_retries_failure_then_reuses_revision(
    catalogue,
):
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import Mock

    from app.domain.errors import CatalogueError
    from app.repositories.cached_vehicle_catalogue import (
        CachedVehicleCatalogue,
    )

    models = catalogue.list_models()
    source = Mock()
    source.list_models.side_effect = [CatalogueError("not ready"), models]
    cached = CachedVehicleCatalogue(source)
    with pytest.raises(CatalogueError):
        cached.list_models()
    with ThreadPoolExecutor(max_workers=4) as pool:
        reads = tuple(pool.map(lambda _: cached.list_models(), range(8)))
    assert all(value is models for value in reads)
    assert source.list_models.call_count == 2
