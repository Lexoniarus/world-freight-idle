"""Account isolation, security, persistence and concurrent economy tests."""

import pytest

from app.api.v1.game_projection import (
    project_state,
    project_vehicle,
)
from app.bootstrap import (
    build_player_service,
)
from app.services.gameplay.fleet import FleetService
from tests.support.catalogues import BERLIN_UID

PASSWORD = "test-only-password-42"


def test_player_service_isolation_and_atomic_purchases(
    synthetic_runtime, synthetic_game, synthetic_vehicle_catalogue
):
    with synthetic_runtime.database.connect() as connection:
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("alice", "alice", "test-only"),
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, 0)",
            ("bob", "bob", "test-only"),
        )
    alice = build_player_service(synthetic_runtime, "alice")
    bob = build_player_service(synthetic_runtime, "bob")
    assert alice.market_lifecycle.scope.world is synthetic_runtime.world
    assert bob.market_lifecycle.scope.world is synthetic_runtime.world
    vehicle = project_vehicle(
        FleetService(
            alice.unit_of_work,
            synthetic_vehicle_catalogue,
            synthetic_runtime.world,
        ).purchase("iveco_sway_500")
    )
    assert alice.get_vehicle(vehicle["id"]).capacity_tons == 24.2
    assert alice.state().player.cash == 26000
    assert bob.state().player.cash == 175000
    assert len(bob.list_vehicles()) == 1
    with pytest.raises(ValueError, match="Nicht genug"):
        project_vehicle(
            FleetService(
                alice.unit_of_work,
                synthetic_vehicle_catalogue,
                synthetic_runtime.world,
            ).purchase("renault_t_high_520")
        )
    with pytest.raises(ValueError, match="Unbekanntes"):
        project_vehicle(
            FleetService(
                alice.unit_of_work,
                synthetic_vehicle_catalogue,
                synthetic_runtime.world,
            ).purchase("fake")
        )
    with pytest.raises(KeyError):
        bob.get_vehicle(vehicle["id"])
    restored = build_player_service(synthetic_runtime, "alice")
    assert project_state(restored.state())["player"]["cash"] == 26000
    assert (
        project_vehicle(restored.get_vehicle(vehicle["id"]))["hub_id"]
        == BERLIN_UID
    )
