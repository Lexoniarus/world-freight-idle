"""Game clock and idempotent player-state initialization."""

from __future__ import annotations

import time
from dataclasses import replace
from unittest.mock import Mock

import pytest

from app.api.v1.game_projection import (
    project_dashboard,
    project_vehicle,
)
from app.api.v1.location_projection import project_location
from app.domain.errors import WorldCatalogueError
from app.domain.game import PlayerState
from app.domain.world_scopes import WorldScope
from app.services.gameplay.fleet import resolve_delivery_facility
from tests.support.game_service import FixturePlayerGameFacade


def test_now_returns_wall_clock(synthetic_game: FixturePlayerGameFacade):
    before = time.time()
    observed = synthetic_game.now()
    after = time.time()
    assert before <= observed <= after


def test_ensure_initial_state_is_idempotent(
    synthetic_game: FixturePlayerGameFacade,
):
    before = [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ]
    synthetic_game.ensure_initial_state()
    assert [
        project_vehicle(item)
        for item in synthetic_game.state_repository.list_vehicles()
    ] == before
    assert synthetic_game.player_state().cash == 175000


def test_reset_restores_playable_state(
    synthetic_game: FixturePlayerGameFacade,
):
    demand = Mock()
    synthetic_game.initialization.market_demand = demand
    synthetic_game.state_repository.save_player(
        PlayerState(cash=1, completed=99, reputation=99)
    )
    state = project_dashboard(synthetic_game.reset())
    assert state["player"]["cash"] == 175000
    assert state["player"]["completed"] == 0
    assert len(state["vehicles"]) == 1
    demand.invalidate.assert_called_once_with()


def test_delivery_requires_verified_catalogue_endpoint(
    synthetic_world_catalogue,
):
    snapshot = synthetic_world_catalogue.read()
    delivery = resolve_delivery_facility(synthetic_world_catalogue)
    berlin = WorldScope(snapshot).facility("berlin_westhafen")
    assert delivery.facility_uid == berlin.facility_uid
    assert delivery.resolution_status == "resolved"
    assert delivery.coordinate_evidence
    assert delivery.company is not None
    assert berlin.company is not None
    assert delivery.company.company_uid == berlin.company.company_uid
    payload = project_location(delivery)
    assert "handled_goods" not in payload
    assert "cargo" not in payload
    assert "sources" not in payload

    for facilities in (
        (),
        (replace(berlin, coordinate_evidence=()),),
    ):
        world = Mock(
            read=Mock(return_value=replace(snapshot, facilities=facilities))
        )
        with pytest.raises(WorldCatalogueError):
            resolve_delivery_facility(world)
