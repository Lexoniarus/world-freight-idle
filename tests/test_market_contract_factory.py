"""Deterministic market selection and immutable contract construction."""

from dataclasses import replace

import pytest

from app.services.market.randomness import DeterministicMarketRandom


def test_deterministic_market_random_is_stable_and_rejects_bad_choices(
    stock_game,
):
    """Keep market terms reproducible without reusing offer identities."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    first = game.market.factory.build(candidate, 10, "stable-context")
    second = game.market.factory.build(candidate, 10, "stable-context")
    assert first.id != second.id
    assert replace(second, id=first.id) == first
    random = DeterministicMarketRandom()
    selected = random.weighted_index(("a", "b"), (1.0, 2.0), "context")
    reversed_selected = random.weighted_index(
        ("b", "a"), (2.0, 1.0), "context"
    )
    assert ("a", "b")[selected] == ("b", "a")[reversed_selected]
    assert 0 < random.fraction("context") < 1
    for identities, weights in (
        ((), ()),
        (("a",), ()),
        (("a", "a"), (1.0, 1.0)),
        (("a",), (0.0,)),
    ):
        with pytest.raises(ValueError):
            random.weighted_index(identities, weights, "context")


def test_contract_factory_draw_is_context_stable_with_fresh_identity(
    stock_game,
):
    """Keep vehicle and load draws stable while identities remain unique."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    factory = game.market.factory
    first = factory._draw_offer(candidate, "stable-draw")
    second = factory._draw_offer(
        replace(candidate, vehicles=tuple(reversed(candidate.vehicles))),
        "stable-draw",
    )
    assert first.vehicle == second.vehicle
    assert first.load_factor == second.load_factor
    assert first.offer_id != second.offer_id


def test_contract_factory_derives_terms_from_selected_vehicle(stock_game):
    """Bind quantity and economics to the selected vehicle facts."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    draw = game.market.factory._draw_offer(candidate, "stable-terms")
    terms = game.market.factory._derive_terms(candidate, draw)
    assert 0 < terms.tons <= draw.vehicle.capacity_tons
    assert terms.context.generated_capacity_tons == draw.vehicle.capacity_tons
    assert (
        terms.context.distance_band == candidate.distance_profile.distance_band
    )
    assert terms.context.cargo_value_eur == round(
        terms.tons * candidate.profile.value_eur_per_t
    )


def test_contract_factory_snapshots_catalogue_evidence(stock_game):
    """Persist the chosen identity, terms and source evidence together."""
    game, _, batch = stock_game
    candidate = batch.snapshots.read().candidates[0]
    factory = game.market.factory
    draw = factory._draw_offer(candidate, "stable-snapshot")
    terms = factory._derive_terms(candidate, draw)
    snapshot = factory._build_snapshot(candidate, 123.0, draw, terms)
    assert snapshot.id == draw.offer_id
    assert snapshot.tons == terms.tons
    assert snapshot.market_context == terms.context
    assert snapshot.created_at == 123.0
    assert snapshot.origin_cargo_evidence == candidate.trade.origin_cargo
    assert snapshot.destination_cargo_evidence == (
        candidate.trade.destination_cargo
    )
