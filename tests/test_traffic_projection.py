"""Public traffic projection contracts independent of persistence and HTTP."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict

from app.api.v1.traffic_projection import project_traffic
from app.composition.player import build_traffic_reader
from app.domain.company_colors import player_color
from app.domain.read_ports import MovementSegment, SharedTransport

ROUTE = {
    "type": "LineString",
    "coordinates": [[13.0, 52.0], [9.0, 53.0]],
}


def shared_transport(
    *,
    user_id: str,
    username: str,
    transport_id: str,
    company_color: str | None = None,
) -> SharedTransport:
    """Build one complete public transport without persistence fixtures."""
    return SharedTransport(
        user_id=user_id,
        username=username,
        id=transport_id,
        vehicle_id=f"{user_id}-vehicle",
        model_id=f"{user_id}-model",
        model_name=f"{username} model",
        departed_at=10,
        arrives_at=20,
        coordinates=((13.0, 52.0), (9.0, 53.0)),
        distance_km=123.0,
        segments=(MovementSegment("driving", 10, 20, 0, 123),),
        company_color=company_color,
    )


def test_traffic_projection_marks_ownership_without_private_economy(caplog):
    rows = (
        shared_transport(
            user_id="alice-id",
            username="Alice",
            transport_id="alice-trip",
        ),
        shared_transport(
            user_id="bob-id",
            username="Bob",
            transport_id="bob-trip",
            company_color="#e45756",
        ),
    )

    with caplog.at_level(logging.INFO):
        traffic = project_traffic(rows, "alice-id")

    own, other = traffic
    assert own["is_own"] is True
    assert other["is_own"] is False
    assert own["player_color"] == player_color("alice-id")
    assert other["player_color"] == "#e45756"
    assert own["route_geojson"] == ROUTE
    assert own["journey"] == {
        "distance_km": 123.0,
        "segments": [asdict(rows[0].segments[0])],
    }
    assert {
        "payout_eur",
        "operating_cost_eur",
        "profit_eur",
        "contract",
    }.isdisjoint(own)
    assert any(
        record.msg == "Shared map traffic projected"
        and record.data["active_transport_count"] == 2
        and record.data["visible_player_count"] == 2
        for record in caplog.records
    )


def test_empty_traffic_projection_is_an_explicit_snapshot(caplog):
    with caplog.at_level(logging.INFO):
        assert project_traffic((), "alice-id") == []

    assert any(
        record.msg == "Shared map traffic projected"
        and record.data["active_transport_count"] == 0
        for record in caplog.records
    )


def test_player_color_is_stable_and_changes_between_users():
    assert player_color("alice-id") == player_color("alice-id")
    assert player_color("alice-id") != player_color("bob-id")
    assert re.fullmatch(r"#[0-9a-f]{6}", player_color("alice-id"))


def test_traffic_reader_builder_reuses_the_runtime_snapshot(synthetic_runtime):
    assert (
        build_traffic_reader(synthetic_runtime)
        is synthetic_runtime.public_traffic
    )
