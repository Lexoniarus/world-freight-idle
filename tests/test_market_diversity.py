"""City market selection, coverage and immutable materialization behavior."""

from dataclasses import replace

from app.domain.contracts import ContractOffer
from app.domain.geography import Coordinates


def test_market_diversity_counts_only_persisted_offer_dimensions(city_market):
    from app.services.market.diversity import MarketDiversity

    market, owned, fleet, _, _ = city_market
    candidates = market.candidates.build(
        (owned.location.city.city_uid,), fleet
    )
    candidate = candidates[0]
    diversity = MarketDiversity()
    assert diversity.rank(candidate) == (0, 0, 0)
    trade = candidate.trade
    diversity.record(
        trade.origin.facility_uid,
        trade.destination.facility_uid,
        trade.cargo.nhm_row_id,
        trade.destination.address.city.city_uid,
    )
    assert diversity.rank(candidate) == (1, 1, 1)
    offer = ContractOffer.from_snapshot(
        market.contract_factory.build(candidate, 1, "visible-diversity")
    )
    visible = MarketDiversity()
    assert visible.rank_offer(offer) == (0, 0, 0, 0)
    visible.record_offer(offer)
    assert visible.rank_offer(offer) == (1, 1, 1, 1)


def test_retention_requires_structure_and_actual_vehicle_compatibility(
    city_market,
):
    market, owned, fleet, world, _ = city_market
    candidate = market.candidates.build(
        (owned.location.city.city_uid,), fleet
    )[0]
    offer = ContractOffer.from_snapshot(
        market.contract_factory.build(candidate, 1000)
    )
    context = offer.market_context
    assert context is not None
    assert market.candidates.structurally_current(offer)
    assert market.candidates.eligible_ids(offer, fleet) == (owned.id,)
    assert not market.candidates.eligible_ids(
        replace(offer, market_model="nhm_v1", market_context=None), fleet
    )
    assert not market.candidates.eligible_ids(
        replace(
            offer,
            market_context=replace(context, transport_class="special"),
        ),
        fleet,
    )
    assert not market.candidates.structurally_current(
        replace(offer, origin=replace(offer.origin, facility_uid="missing"))
    )
    assert not market.candidates.structurally_current(
        replace(
            offer, origin=replace(offer.origin, coordinates=Coordinates(0, 0))
        )
    )
    assert not market.candidates.structurally_current(
        replace(
            offer,
            market_context=replace(context, transport_class="special"),
        )
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
