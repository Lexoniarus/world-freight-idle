"""Audit reports and inventory stay local and preserve routing boundaries."""

from dataclasses import replace

import pytest

from app.domain.errors import WorldCatalogueError
from app.repositories.routing_audit import SqliteRoutingAudit
from app.services.routing_inventory import routing_inventory
from tests.test_market_preparation import bind_preparation


def test_audit_inventory_is_structural_and_report_preserves_history(
    game, database
):
    preparation = bind_preparation(game, database)
    world = game.world.read()
    pairs = tuple(routing_inventory(world, "Berlin"))
    assert pairs
    assert len(pairs) == len(set(pairs))
    assert tuple(routing_inventory(world, "missing-city")) == ()
    empty = replace(world, facilities=())
    with pytest.raises(WorldCatalogueError):
        tuple(routing_inventory(empty))
    no_goods = replace(
        world,
        facilities=tuple(
            replace(f, nhm_profiles=()) for f in world.facilities[:2]
        ),
    )
    assert tuple(routing_inventory(no_goods)) == ()
    with_unroutable = replace(
        world,
        facilities=(
            *world.facilities[:2],
            replace(world.facilities[2], coordinates=None),
        ),
    )
    assert tuple(routing_inventory(with_unroutable)) is not None
    report = SqliteRoutingAudit(database).report((pairs[0][0],))
    assert report == {
        "relations": [],
        "anchors": [],
        "attempts": [],
        "focused_attempts": [],
    }
    assert preparation.readiness.store.get("missing") is None
