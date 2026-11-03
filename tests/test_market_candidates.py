"""City market selection, coverage and immutable materialization behavior."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.contracts import ContractOffer
from app.domain.errors import CatalogueError, WorldCatalogueError
from app.domain.market_calculations import (
    evidence_weight,
)
from app.domain.market_compatibility import (
    can_carry_offer,
    market_vehicle,
    vehicle_suitability,
)
from app.domain.market_profiles import (
    TransportCapability,
)
from app.services.market.trade_network import TradeNetwork


def test_candidate_build_is_immutable_and_requires_city_scope(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    candidates = market.candidates.build((city,), fleet)
    assert candidates
    first = candidates[0]
    with pytest.raises(FrozenInstanceError):
        first.weight = 0
    assert market.candidates.build((), fleet) == ()


def test_candidate_build_rejects_incompatible_vehicle_mode(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    assert (
        market.candidates.build((city,), (replace(fleet[0], mode="rail"),))
        == ()
    )


def test_vehicle_suitability_uses_scale_and_capability(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    first = market.candidates.build((city,), fleet)[0]
    profile = first.profile
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


def test_evidence_weight_orders_source_and_hierarchy_quality(city_market):
    market, owned, fleet, _, _ = city_market
    city = owned.location.city.city_uid
    first = market.candidates.build((city,), fleet)[0]
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


def test_offer_compatibility_requires_city_capacity_and_profile(city_market):
    market, _, fleet, _, _ = city_market
    candidate = market.candidates.build((fleet[0].city_uid,), fleet)[0]
    offer = ContractOffer.from_snapshot(
        market.contract_factory.build(candidate, 1000)
    )
    profile = candidate.profile
    assert can_carry_offer(fleet[0], offer, profile)
    assert not can_carry_offer(
        replace(fleet[0], city_uid="elsewhere"), offer, profile
    )
    assert not can_carry_offer(
        replace(fleet[0], capacity_tons=0.01), offer, profile
    )


def test_market_vehicle_rejects_model_mismatch_and_active_vehicle(city_market):
    market, owned, _, _, model = city_market
    with pytest.raises(ValueError):
        market_vehicle(owned, replace(model, id="other"), owned.location)
    owned.start_trip()
    with pytest.raises(ValueError):
        market_vehicle(owned, model, owned.location)


def test_candidate_fleet_excludes_active_vehicle(city_market):
    market, owned, _, _, _ = city_market
    owned.start_trip()
    assert market.candidates.resolve_fleet((owned,)) == ()


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


def test_candidate_cache_discards_oldest_context_after_bound(city_market):
    market, _, _, _, _ = city_market
    candidates = market.candidates

    for index in range(33):
        candidates.build((f"missing-city-{index}",), ())

    assert len(candidates._candidate_cache) == 32
    assert (("missing-city-0",), ()) not in candidates._candidate_cache


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
