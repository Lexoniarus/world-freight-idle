"""Incremental stock preparation and reusable supply integration."""

from dataclasses import replace
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_catalogue_changes_block_old_supply_without_deleting_terms(
    stock_game,
):
    from unittest.mock import Mock

    from app.domain.market_profiles import TransportCapability

    game, prep, batch = stock_game
    for _ in range(30):
        if (await batch.process()).status == "ready":
            break
    saved = game.state_repository.list_offers()
    with patch.object(
        game.market_lifecycle.generation.candidates,
        "structurally_current",
        return_value=False,
    ):
        snapshot = batch.snapshots.read()
        assert not snapshot.usable_offers
        assert not snapshot.usable_templates
        assert snapshot.offers == saved
        assert game.list_contracts() == []
    assert game.state_repository.list_offers() == saved
    # A changed freight class must not count incompatible old snapshots as
    # sufficient stock and thereby prevent the worker from replacing them.
    reference = game.market_lifecycle.generation.candidates.reference()
    changed = replace(
        reference,
        market_profiles=tuple(
            replace(p, transport_class="special")
            for p in reference.market_profiles
        ),
    )
    game.market_lifecycle.generation.candidates.world = Mock(
        read=Mock(return_value=changed)
    )
    catalogue = game.market_lifecycle.generation.candidates.catalogue
    models = tuple(
        replace(m, transport_capabilities=(TransportCapability("special", 1),))
        for m in catalogue.list_models()
    )
    with patch.object(catalogue, "list_models", return_value=models):
        assert game.list_contracts() == []
        snapshot = batch.snapshots.read()
        assert snapshot.ready and not snapshot.usable_offers
        assert not snapshot.usable_templates
        for _ in range(30):
            if (await batch.process()).status == "ready":
                break
        available = game.list_contracts()
        assert len(available) == 30
        assert all(
            o.market_context.transport_class == "special" for o in available
        )
    assert game.state_repository.list_offers()[: len(saved)] == saved
