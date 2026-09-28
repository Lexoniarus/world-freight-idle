from __future__ import annotations

import pytest

from app.domain.geography import Coordinates
from app.domain.routing_anchors import RoutingAnchor
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository


def test_routing_anchor_repository_roundtrip(tmp_path):
    database = SqliteGameDatabase(tmp_path / "anchors.db")
    database.initialize()
    repository = SqliteRoutingAnchorRepository(database)
    anchor = RoutingAnchor(
        facility_uid="facility-1",
        routing_profile="truck",
        anchor=Coordinates(52.5, 13.4),
        method="facility_coordinate",
        facility_coordinates=Coordinates(52.51, 13.41),
        snap_distance_m=12.5,
        validation_status="validated",
        provider="Valhalla",
        provider_revision="graph-1",
        validated_at=123.0,
    )

    repository.put(anchor)

    assert repository.get("facility-1", "truck") == anchor
    assert repository.get("missing", "truck") is None


def test_routing_anchor_repository_roundtrips_failure_without_coordinates(
    tmp_path,
):
    database = SqliteGameDatabase(tmp_path / "anchors.db")
    database.initialize()
    repository = SqliteRoutingAnchorRepository(database)
    failure = RoutingAnchor(
        facility_uid="facility-2",
        routing_profile="truck",
        anchor=None,
        method="address_fallback",
        facility_coordinates=None,
        snap_distance_m=None,
        validation_status="geocoding_failed",
        provider="Nominatim + Valhalla",
        provider_revision=None,
        validated_at=456.0,
    )

    repository.put(failure)

    assert repository.get("facility-2", "truck") == failure


def test_routing_anchor_repository_rejects_unknown_persisted_status(tmp_path):
    database = SqliteGameDatabase(tmp_path / "anchors.db")
    database.initialize()
    repository = SqliteRoutingAnchorRepository(database)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO routing_anchors (
                facility_uid, routing_profile, anchor_lat, anchor_lon,
                method, facility_lat, facility_lon, snap_distance_m,
                validation_status, provider, provider_revision, validated_at
            ) VALUES (?, ?, NULL, NULL, ?, NULL, NULL, NULL, ?, ?, NULL, ?)
            """,
            (
                "facility-corrupt",
                "truck",
                "address_fallback",
                "unknown",
                "provider",
                1.0,
            ),
        )

    with pytest.raises(ValueError, match="status"):
        repository.get("facility-corrupt", "truck")
