"""Product hierarchy and facility evidence have separate invariants."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.api.v1.game_projection import project_nhm_profile
from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.evidence import SourceReference


def test_nhm_entities_reject_invalid_hierarchies_and_weights():
    product = NhmProduct(2, "87", "Vehicles", (2, 1))
    profile = FacilityNhmProfile(product, "both", "derived", 0.5, 0.8, None)
    assert replace(profile, role="input").product is product
    assert product.is_compatible_with(product)
    with pytest.raises(FrozenInstanceError):
        setattr(profile, "role", "input")
    for changes in (
        {"nhm_row_id": True},
        {"nhm_row_id": 0},
        {"code": ""},
        {"name": ""},
        {"ancestor_row_ids": []},
        {"ancestor_row_ids": ()},
        {"ancestor_row_ids": (1, 2)},
        {"ancestor_row_ids": (2, 2)},
        {"ancestor_row_ids": (2, -1)},
        {"ancestor_row_ids": (2, 0)},
        {"ancestor_row_ids": (2, True)},
    ):
        with pytest.raises(ValueError):
            replace(product, **changes)
    for changes in (
        {"role": "invalid"},
        {"evidence_type": ""},
        {"confidence": True},
        {"confidence": float("nan")},
        {"confidence": -1},
        {"confidence": 1.1},
        {"priority_score": float("inf")},
        {"priority_score": 1.1},
    ):
        with pytest.raises(ValueError):
            replace(profile, **changes)


def test_nhm_profile_projection_retains_fields_without_mutating_products():
    product = NhmProduct(2, "87", "Vehicles", (2, 1))
    profile = FacilityNhmProfile(product, "both", "derived", 0.5, 0.8, None)
    payload = project_nhm_profile(profile)
    assert payload["code"] == "87" and payload["role"] == "both"
    assert "product" not in payload and payload["source"] is None
    payload["ancestor_row_ids"].clear()
    assert product.ancestor_row_ids == (2, 1)
    source = SourceReference("https://source.test", "official", "2026-09-20")
    documented = replace(profile, evidence_type="official", source=source)
    assert project_nhm_profile(documented)["source"]["url"] == source.url
