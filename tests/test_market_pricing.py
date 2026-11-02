"""Freight-rate and operating-cost pricing responsibilities."""

from dataclasses import replace

from app.domain.economics import CostBreakdown
from app.domain.pricing import calculate_price


def test_freight_rate_changes_payout_but_cargo_value_does_not(synthetic_game):
    offer = synthetic_game.list_contracts()[0]
    costs = CostBreakdown(
        "test",
        0.5,
        "diesel",
        "l",
        1.5,
        80,
        200,
        (),
        0,
        280,
    )
    base = calculate_price(offer.tons, 400, costs, offer.rate_eur_per_km_ton)
    assert calculate_price(
        offer.tons,
        800,
        costs,
        offer.rate_eur_per_km_ton,
    ).payout_eur > base.payout_eur
    assert calculate_price(
        offer.tons * 2,
        400,
        costs,
        offer.rate_eur_per_km_ton,
    ).payout_eur > base.payout_eur
    assert calculate_price(
        offer.tons,
        400,
        costs,
        offer.rate_eur_per_km_ton * 2,
    ).payout_eur > base.payout_eur
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
    assert calculate_price(
        changed.tons,
        400,
        costs,
        changed.rate_eur_per_km_ton,
    ) == base
    assert calculate_price(
        offer.tons,
        400,
        replace(costs, maintenance_cost_eur=400, total_cost_eur=480),
        offer.rate_eur_per_km_ton,
    ).operating_cost_eur > base.operating_cost_eur
