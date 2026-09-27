"""Search evidence must survive without premature global publication."""

import pytest

from app.domain.errors import GeocodingError
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
async def test_candidate_search_keeps_evidence_and_never_changes_saved_anchor(
    tmp_path,
):
    database, evidence = routing_store(tmp_path)
    anchors = SqliteRoutingAnchorRepository(database)
    locator = FakeLocator([located(accepted=False), located()])
    resolver = RoutingAnchorResolver(
        anchors,
        locator,
        FakeGeocoder((52.52, 13.405, "resolved")),
        1000,
        lambda: 1,
        evidence,
    )
    result = await resolver.resolve(facility())
    assert result[0].method == "address_fallback"
    assert anchors.get("facility-1", "truck") is None
    with database.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM routing_attempts").fetchone()[0]
            == 2
        )
    resolver._geocoder = FakeGeocoder(error=GeocodingError("not found"))
    locator.results = [located()]
    assert await resolver.resolve(facility(), force=True)
