"""Typed and reproducible economy audit composition."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from random import Random
from unittest.mock import Mock

import pytest

from app.bootstrap import build_economy_audit
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.economy_audit import EconomyAuditService, summarize_economy


def test_economy_audit_is_typed_and_reproducible():
    root = Path(__file__).resolve().parents[1]
    service = build_economy_audit(root, 20260925)
    assert isinstance(service.vehicles, SqliteVehicleCatalogue)
    assert isinstance(service.world, SqliteWorldCatalogue)
    models = service.vehicles.list_models()[:1]
    world = service.world.read()
    catalogue = Mock()
    catalogue.list_models.return_value = models
    worlds = Mock()
    worlds.read.return_value = replace(
        world,
        market_profiles=world.market_profiles[:20],
    )
    first = EconomyAuditService(catalogue, worlds, Random(20260925)).matrix()
    second = EconomyAuditService(catalogue, worlds, Random(20260925)).matrix()
    assert first == second
    assert any(row.compatible for row in first)
    assert any(not row.compatible for row in first)
    summary = summarize_economy(first)
    assert summary.models == 1
    assert summary.rows == len(first)
    assert summary.reference_min_margin >= 0.2
    with pytest.raises(FrozenInstanceError):
        setattr(first[0], "compatible", False)
