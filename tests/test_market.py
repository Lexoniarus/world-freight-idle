"""City market selection, coverage and immutable materialization behavior."""

import math
import random
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.bootstrap import build_market_generator
from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.contracts import ContractOffer
from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.geography import Coordinates
from app.domain.market_calculations import (
    distance_band,
    evidence_weight,
    great_circle_km,
    shipment_tons,
)
from app.domain.market_compatibility import (
    can_carry_offer,
    market_vehicle,
    vehicle_suitability,
)
from app.domain.market_profiles import (
    VEHICLE_SCALES,
    DistanceLoadProfile,
    NhmMarketProfile,
    TransportCapability,
    VehicleScaleProfile,
)
from app.domain.world_scopes import WorldScope
from app.services.fleet import build_owned_vehicle
from app.services.market_scope import MarketScopeResolver
from app.services.trade_network import TradeNetwork


@pytest.fixture
def city_market(world_catalogue, catalogue):
    snapshot = world_catalogue.read()
    base = WorldScope(snapshot).facility("berlin_westhafen")
    cargo = NhmProduct(1, "7308", "Structural modules", (1,))
    output = FacilityNhmProfile(cargo, "output", "derived", 0.8, 0.7, None)
    inbound = replace(output, role="input")
    origin = replace(base, facility_uid="origin-a", nhm_profiles=(output,))
    other = replace(origin, facility_uid="origin-b")
    destinations = tuple(
        replace(
            base,
            facility_uid="destination-" + str(index),
            address=replace(
                base.address,
                city=replace(
                    base.address.city,
                    city_uid=str(UUID(int=index + 1)),
                ),
            ),
            coordinates=point,
            nhm_profiles=(inbound,),
        )
        for index, point in enumerate(
            (Coordinates(52.5, 13.4), Coordinates(50, 13), Coordinates(40, 2))
        )
    )
    # An inbound facility in the active city cannot invent outbound work.
    inactive = replace(
        origin, facility_uid="inbound-only", nhm_profiles=(inbound,)
    )
    profile = NhmMarketProfile(
        1,
        "general",
        500,
        1.4,
        tuple(
            DistanceLoadProfile(band, 1, 0.5, 0.8)
            for band in ("short", "medium", "long")
        ),
        tuple(VehicleScaleProfile(scale, 1) for scale in VEHICLE_SCALES),
    )
    world = Mock(
        read=Mock(
            return_value=replace(
                snapshot,
                facilities=(origin, other, inactive, *destinations),
                market_profiles=(profile,),
            )
        )
    )
    model = next(
        m for m in catalogue.list_models() if m.id == "iveco_sway_500"
    )
    models = Mock(list_models=Mock(return_value=(model,)))
    owned = build_owned_vehicle(model, "truck", origin.location_snapshot())
    market = build_market_generator(world, random.Random(3), models)
    fleet = market.candidates.resolve_fleet((owned,))
    return market, owned, fleet, world, model


def test_city_scope_uses_only_distinct_idle_city_identities(city_market):
    market, owned, _, world, model = city_market
    scope = MarketScopeResolver(world)
    other = build_owned_vehicle(model, "other", owned.location)
    busy = build_owned_vehicle(model, "busy", owned.location)
    busy.start_trip()
    assert scope.resolve((owned, other, busy)) == (
        owned.location.city.city_uid,
    )
    assert scope.resolve((busy,)) == ()
    destination = world.read().facilities[-1].location_snapshot()
    other.reposition_within_city(owned.location)
    other.start_trip()
    other.arrive(destination)
    assert len(scope.resolve((owned, other))) == 2
    # Same city name is not a shared identity.
    assert other.location is not None
    assert other.location.city.name == owned.location.city.name
    owned._location = None
    assert scope.resolve((owned,)) == (
        world.read().facilities[0].address.city.city_uid,
    )


def test_distance_and_tonnage_are_deterministic_and_bounded():
    assert [distance_band(d) for d in (0, 150, 150.0001, 600, 600.0001)] == [
        "short",
        "short",
        "medium",
        "medium",
        "long",
    ]
    assert great_circle_km(Coordinates(0, 0), Coordinates(0, 0)) == 0
    assert great_circle_km(
        Coordinates(0, 0), Coordinates(0, 180)
    ) == pytest.approx(20015.1144, rel=1e-6)
    assert great_circle_km(
        Coordinates(0, 179), Coordinates(0, -179)
    ) == pytest.approx(222.39, rel=1e-4)
    for bad in (-1, math.nan, math.inf):
        with pytest.raises(ValueError):
            distance_band(bad)
    assert shipment_tons(0.01, 0.5) == 0.01
    assert shipment_tons(1.157, 1) == 1.15
    assert shipment_tons(24.2, 0.5) == 12.1
    for capacity, load in ((0, 1), (1, 0), (1, 1.1), (math.inf, 0.5)):
        with pytest.raises(ValueError):
            shipment_tons(capacity, load)


def test_candidate_compatibility_and_weighting_are_separate(city_market):
    market, owned, fleet, world, model = city_market
    city = owned.location.city.city_uid
    candidates = market.candidates.build((city,), fleet)
    assert candidates
    first = candidates[0]
    with pytest.raises(FrozenInstanceError):
        first.weight = 0
    profile = first.profile
    assert market.candidates.build((), fleet) == ()
    assert (
        market.candidates.build((city,), (replace(fleet[0], mode="rail"),))
        == ()
    )
    assert (
        vehicle_suitability(replace(fleet[0], capabilities=()), profile) == 0
    )
    zero = replace(
        profile,
        scale_profiles=tuple(
            replace(p, suitability_game=0) for p in profile.scale_profiles
        ),
    )
    assert vehicle_suitability(fleet[0], zero) == 0
    assert market.candidates._candidate(first.trade, ()) is None
    market.candidates._profiles[1] = replace(
        profile,
        distance_profiles=tuple(
            replace(p, selection_weight=0) for p in profile.distance_profiles
        ),
    )
    assert market.candidates._candidate(first.trade, fleet) is None
    market.candidates._profiles[1] = profile
    low = replace(
        fleet[0],
        vehicle_id="low",
        capacity_tons=1,
        capabilities=(TransportCapability("general", 0.2),),
    )
    candidate = market.candidates._candidate(first.trade, (*fleet, low))
    assert candidate.weight == pytest.approx(evidence_weight(first.trade))
    assert [v.suitability for v in candidate.vehicles] == [1, 0.2]
    documented = replace(
        first.trade,
        origin_cargo=replace(
            first.trade.origin_cargo, evidence_type="official"
        ),
        destination_cargo=replace(
            first.trade.destination_cargo, evidence_type="official"
        ),
    )
    assert evidence_weight(documented) > evidence_weight(first.trade)
    assert evidence_weight(
        replace(first.trade, match_type="ancestor")
    ) < evidence_weight(first.trade)
    assert evidence_weight(
        replace(
            first.trade,
            origin_cargo=replace(
                first.trade.origin_cargo, confidence=0, priority_score=0
            ),
        )
    ) < evidence_weight(first.trade)
    # Candidate max never forces the later materialization vehicle.
    with patch.object(
        market.factory.rng, "choices", return_value=[candidate.vehicles[1]]
    ) as choose:
        offer = ContractOffer.from_snapshot(
            market.factory.build(candidate, 1000)
        )
    assert choose.call_args.kwargs["weights"] == [1, 0.2]
    assert offer.market_context is not None
    assert offer.market_context.generated_capacity_tons == 1
    assert 0.5 <= offer.tons <= 0.8
    assert can_carry_offer(fleet[0], offer, profile)
    assert not can_carry_offer(
        replace(fleet[0], city_uid="elsewhere"), offer, profile
    )
    assert not can_carry_offer(
        replace(fleet[0], capacity_tons=0.01), offer, profile
    )
    with pytest.raises(ValueError):
        market_vehicle(owned, replace(model, id="other"), owned.location)
    owned.start_trip()
    assert market.candidates.resolve_fleet((owned,)) == ()
    with pytest.raises(ValueError):
        market_vehicle(owned, model, owned.location)


def test_city_coverage_preserves_ids_and_never_invents_relations(city_market):
    market, owned, fleet, world, _ = city_market
    cities = (owned.location.city.city_uid,)
    offers, diagnostics = market.generate(1000, cities, fleet)
    assert len(offers) == 9
    assert (
        diagnostics[0].covered_facilities
        == diagnostics[0].eligible_facilities
        == 2
    )
    assert diagnostics[0].distance_counts == (3, 3, 3)
    assert diagnostics[0].unmet_bands == ()
    assert {o.origin.facility_uid for o in offers} == {"origin-a", "origin-b"}
    assert len({o.id for o in offers}) == 9
    assert all(
        o.market_model == "nhm_v2" and o.cargo_system == "NHM2026"
        for o in offers
    )
    assert all(
        o.origin.facility_uid != o.destination.facility_uid for o in offers
    )
    assert any(o.destination.city.city_uid not in cities for o in offers)
    assert market.generate(1001, cities, fleet, offers)[0] == offers
    assert market.generate(1001, (), (), ())[0] == ()
    network = market.candidates._network
    assert set(network._options_by_origin) <= {
        "origin-a",
        "origin-b",
        "inbound-only",
    }
    candidates = market.candidates.build(cities, fleet)
    long_only = tuple(
        c for c in candidates if c.distance_profile.distance_band == "long"
    )[:1]
    plan = market.coverage.plan(cities, long_only, ())
    assert len(plan.selected) == 3
    assert plan.diagnostics[0].unmet_bands == ("short", "medium")
    empty = market.coverage.plan(cities, (), ())
    assert empty.selected == ()
    assert empty.diagnostics[0].unmet_bands == ("short", "medium", "long")
    more_origins = tuple(
        replace(
            long_only[0],
            trade=replace(
                long_only[0].trade,
                origin=replace(long_only[0].trade.origin, facility_uid=str(i)),
            ),
        )
        for i in range(12)
    )
    assert len(market.coverage.plan(cities, more_origins, ()).selected) == 12


def test_materialization_snapshots_profile_terms_and_validates_context(
    city_market,
):
    market, owned, fleet, _, _ = city_market
    offers, _ = market.generate(1000, (owned.location.city.city_uid,), fleet)
    for offer in offers:
        context = offer.market_context
        assert offer.expires_at == 22600
        assert offer.payload_band == ""
        assert offer.rate_eur_per_km_ton == pytest.approx(0.18 * 1.4)
        assert context.cargo_value_eur == round(offer.tons * 500)
        assert (
            0.5 * owned.capacity_tons - 0.01
            <= offer.tons
            <= 0.8 * owned.capacity_tons
        )
        assert context.generated_capacity_tons == owned.capacity_tons
    first = offers[0]
    for changes in (
        {"distance_band": "invalid"},
        {"transport_class": "bad"},
        {"generated_for_vehicle_scale": "bad"},
        {"generated_capacity_tons": 0},
        {"cargo_value_eur_per_t": 0},
        {"cargo_value_eur": -1},
    ):
        with pytest.raises(ValueError):
            replace(first.market_context, **changes)
    with pytest.raises(ValueError):
        replace(first, market_context=None)
    with pytest.raises(ValueError):
        replace(first, cargo_system="other")
    with pytest.raises(ValueError):
        replace(first, tons=owned.capacity_tons + 1)
    with pytest.raises(ValueError):
        replace(
            first,
            market_context=replace(first.market_context, cargo_value_eur=1),
        )
    historical = replace(first, market_model="nhm_v1", market_context=None)
    assert historical.market_context is None


def test_reference_cache_and_empty_origin_relations(city_market):
    market, owned, fleet, world, _ = city_market
    city = owned.location.city.city_uid
    first = market.candidates.build((city,), fleet)
    network = market.candidates._network
    assert market.candidates.build((city,), fleet) == first
    assert market.candidates._network is network
    assert network.options_for("inbound-only") == ()
    with pytest.raises(WorldCatalogueError):
        network.options_for("unknown")
    with pytest.raises(WorldCatalogueError):
        TradeNetwork(())
    snapshot = world.read()
    updated = replace(snapshot.facilities[0], label="New source")
    world.read.return_value = replace(
        snapshot, facilities=(updated, *snapshot.facilities[1:])
    )
    second = market.candidates.build((city,), fleet)
    assert market.candidates._network is not network
    assert second[0].trade.origin.label == "New source"
    assert first[0].trade.origin.label != "New source"


def test_model_resolution_is_explicit_and_saved_capacity_wins(city_market):
    market, owned, fleet, world, _ = city_market
    owned._capacity_tons = 4.2
    owned._location = None
    assert market.candidates.resolve_fleet((owned,))[0].capacity_tons == 4.2
    for identifier in (None, "unknown"):
        owned._model_id = identifier
        with pytest.raises(ValueError, match="Bestand"):
            market.candidates.resolve_fleet((owned,))
    market.candidates.catalogue.list_models.side_effect = CatalogueError(
        "offline"
    )
    with pytest.raises(CatalogueError):
        market.candidates.resolve_fleet((owned,))


def test_retention_requires_structure_and_actual_vehicle_compatibility(
    city_market,
):
    market, owned, fleet, world, _ = city_market
    offer = market.generate(1000, (owned.location.city.city_uid,), fleet)[0][0]
    assert market.candidates.structurally_current(offer)
    assert market.candidates.eligible_ids(offer, fleet) == (owned.id,)
    assert not market.candidates.eligible_ids(
        replace(offer, market_model="nhm_v1", market_context=None), fleet
    )
    assert not market.candidates.eligible_ids(
        replace(
            offer,
            market_context=replace(
                offer.market_context, transport_class="special"
            ),
        ),
        fleet,
    )
    assert not market.candidates.structurally_current(
        replace(offer, origin=replace(offer.origin, facility_uid="missing"))
    )
    assert not market.candidates.structurally_current(
        replace(offer, market_model="nhm_v1", market_context=None)
    )
    profile = market.candidates._profiles.pop(1)
    assert not market.candidates.structurally_current(offer)
    assert not market.candidates.eligible_ids(offer, fleet)
    market.candidates._profiles[1] = replace(
        profile,
        distance_profiles=tuple(
            replace(p, selection_weight=0) for p in profile.distance_profiles
        ),
    )
    assert not market.candidates.structurally_current(offer)
    market.candidates._profiles[1] = profile
    assert not market.candidates.structurally_current(
        replace(
            offer,
            origin_cargo_evidence=replace(
                offer.origin_cargo_evidence, confidence=0
            ),
        )
    )


def test_candidate_value_invariants_reject_invalid_context(city_market):
    market, owned, fleet, _, _ = city_market
    candidate = market.candidates.build((fleet[0].city_uid,), fleet)[0]
    for changes in (
        {"weight": 0},
        {"weight": float("inf")},
        {"vehicles": ()},
        {"profile": replace(candidate.profile, nhm_row_id=999)},
        {
            "distance_profile": replace(
                candidate.distance_profile, selection_weight=0
            )
        },
        {
            "vehicles": (
                replace(
                    candidate.vehicles[0],
                    vehicle=replace(fleet[0], city_uid="elsewhere"),
                ),
            )
        },
    ):
        with pytest.raises(ValueError):
            replace(candidate, **changes)
    for changes in (
        {"model_id": ""},
        {"capacity_tons": 0},
        {"scale": "invalid"},
    ):
        with pytest.raises(ValueError):
            replace(fleet[0], **changes)
    for weight in (0, -1, 2):
        with pytest.raises(ValueError):
            replace(candidate.vehicles[0], suitability=weight)
