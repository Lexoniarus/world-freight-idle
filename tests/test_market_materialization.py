"""City market selection, coverage and immutable materialization behavior."""

from dataclasses import replace

import pytest

from app.domain.contracts import ContractOffer


def test_materialization_snapshots_profile_terms_and_validates_context(
    city_market,
):
    market, owned, fleet, _, _ = city_market
    candidates = market.candidates.build(
        (owned.location.city.city_uid,), fleet
    )
    offers = tuple(
        ContractOffer.from_snapshot(
            market.contract_factory.build(candidate, 1000)
        )
        for candidate in candidates[:9]
    )
    for offer in offers:
        context = offer.market_context
        assert context is not None
        assert offer.expires_at is None
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
    first_context = first.market_context
    assert first_context is not None
    for changes in (
        {"distance_band": "invalid"},
        {"transport_class": "bad"},
        {"generated_for_vehicle_scale": "bad"},
        {"generated_capacity_tons": 0},
        {"cargo_value_eur_per_t": 0},
        {"cargo_value_eur": -1},
    ):
        with pytest.raises(ValueError):
            replace(first_context, **changes)
    with pytest.raises(ValueError):
        replace(first, market_context=None)
    with pytest.raises(ValueError):
        replace(first, cargo_system="other")
    with pytest.raises(ValueError):
        replace(first, tons=owned.capacity_tons + 1)
    with pytest.raises(ValueError):
        replace(
            first,
            market_context=replace(first_context, cargo_value_eur=1),
        )
    historical = replace(first, market_model="nhm_v1", market_context=None)
    assert historical.market_context is None
