"""Real candidate repair retains failed evidence and fences late writers."""

import asyncio
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.errors import GeocodingError
from app.domain.geography import Coordinates
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.services.routing_anchors import RoutingAnchorResolver
from tests.test_routing_anchors import (
    FakeGeocoder,
    FakeLocator,
    facility,
    located,
)
from tests.test_routing_readiness_store import routing_store


@pytest.mark.asyncio
async def test_osm_repair_preserves_each_failure_and_rejects_lost_lease(
    tmp_path,
):
    database, evidence = routing_store(tmp_path)
    anchors = SqliteRoutingAnchorRepository(database)
    item = facility()
    candidate = Coordinates(52.5202, 13.4052)
    locator = FakeLocator(
        [
            replace(
                located(distance=500), candidates=(item.coordinates, candidate)
            ),
            located(coordinates=candidate),
        ]
    )
    resolver = RoutingAnchorResolver(
        anchors,
        locator,
        FakeGeocoder(error=GeocodingError("not found")),
        250,
        lambda: 1,
        evidence,
    )
    result = await resolver.resolve(item)
    assert result.method == "osm_access"
    with database.connect() as conn:
        assert [
            r[0]
            for r in conn.execute(
                "SELECT outcome FROM routing_attempts ORDER BY attempt_id"
            )
        ] == ["snap_too_far", "geocoding_failed", "validated"]
    locator.results = [located()]
    with patch.object(anchors, "put_leased", return_value=False):
        with pytest.raises(TimeoutError):
            await resolver.resolve(item, force=True)
    locator.results = [located()]
    assert evidence.acquire("anchor:facility-1:truck", "other", 1, 20)
    task = asyncio.create_task(resolver.resolve(item, force=True))
    await asyncio.sleep(0.11)
    evidence.release("anchor:facility-1:truck", "other")
    assert (await task).validation_status == "validated"


@pytest.mark.asyncio
async def test_transient_geocoder_failure_never_forces_osm_repair(tmp_path):
    database, evidence = routing_store(tmp_path)
    anchors = SqliteRoutingAnchorRepository(database)
    error = GeocodingError("temporary")
    error.retryable = True
    locator = FakeLocator(
        [replace(located(distance=500), candidates=(Coordinates(51, 10),))]
    )
    resolver = RoutingAnchorResolver(
        anchors, locator, FakeGeocoder(error=error), 250, lambda: 1, evidence
    )
    result = await resolver.resolve(facility())
    assert result.validation_status == "provider_unavailable"
    assert len(locator.calls) == 1


@pytest.mark.asyncio
async def test_anchor_address_change_invalidates_cached_access(tmp_path):
    database, evidence = routing_store(tmp_path)
    anchors = SqliteRoutingAnchorRepository(database)
    item = facility()
    locator = FakeLocator([located(), located()])
    resolver = RoutingAnchorResolver(
        anchors, locator, FakeGeocoder(), 250, lambda: 1, evidence
    )
    first = await resolver.resolve(item)
    assert await resolver.resolve(item) == first
    changed = replace(
        item, address=replace(item.address, street="Changed street")
    )
    second = await resolver.resolve(changed)
    assert first.source_fingerprint != second.source_fingerprint
    assert len(locator.calls) == 2
    assert anchors.get(item.facility_uid, "truck") == second
