"""Canonical historical documents stay independent of public projections."""

import json
from dataclasses import asdict, replace

import pytest

from app.api.v1.game_projection import project_contract
from app.repositories.snapshot_mapping import (
    load_cargo,
    load_location,
    load_offer,
)


def test_canonical_snapshots_preserve_facts_and_reject_public_documents(game):
    offer = game.state_repository.list_offers()[0]
    encoded = json.loads(json.dumps(asdict(offer)))
    assert load_offer(encoded) == offer
    assert load_location(encoded["origin"]) == offer.origin
    assert load_cargo(encoded["cargo"]) == offer.cargo
    assert "origin_hub_id" not in encoded
    assert "id" not in encoded["origin"]
    assert "company_uid" not in encoded["origin"]
    assert isinstance(encoded["cargo"], dict)
    location = replace(offer.origin, company=None, coordinate_evidence=())
    cargo = replace(offer.cargo, source=None)
    assert load_location(asdict(location)) == location
    assert load_cargo(asdict(cargo)) == cargo
    for loader, value, required in (
        (load_location, encoded["origin"], "aliases"),
        (load_cargo, encoded["cargo"], "ancestor_row_ids"),
        (load_offer, encoded, "origin"),
    ):
        broken = {key: item for key, item in value.items() if key != required}
        with pytest.raises(KeyError):
            loader(broken)
        with pytest.raises(TypeError):
            loader({**value, "unrecognized_field": "invalid"})
    with pytest.raises(TypeError):
        load_offer(project_contract(offer))
    with pytest.raises(ValueError):
        load_offer({**encoded, "tons": True})
