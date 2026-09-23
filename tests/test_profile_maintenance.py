"""Maintenance boundaries, atomic changes and CLI backup ordering."""

import asyncio
import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_player,
    project_transport,
    project_vehicle,
)
from app.bootstrap import (
    build_player_service,
    build_profile_maintenance_service,
)
from app.domain.game import OwnedVehicle, PlayerState
from app.repositories.accounts import AccountRepository
from app.repositories.database_backup import backup_database
from scripts.update_test_profile import main, parse_assignments
from tests.test_api import make_settings
from tests.test_game import first_berlin_contract
from tests.transport_fixtures import add_transport


def test_profile_update_preserves_other_players_and_trip_snapshots(
    database, runtime, game, catalogue, tmp_path
):
    service = build_profile_maintenance_service(
        replace(
            make_settings(tmp_path),
            db_path=database.path,
            vehicle_catalogue_path=catalogue.path,
        )
    )

    accounts = AccountRepository(database)
    user = accounts.create_user("Selected", "not-a-real-hash")
    selected = build_player_service(runtime, user["id"])
    other = accounts.create_user("Untouched", "not-a-real-hash")
    other_game = build_player_service(runtime, other["id"])
    add_transport(selected, payout=123, arrives_at=9999999999, tons=24)
    before = [
        asdict(item)
        for item in selected.state_repository.list_transports()
        if item.status == "active"
    ]
    other_before = project_player(other_game._get_player())
    backup = tmp_path / "backup.db"
    backup_database(database.path, backup)
    assert backup.exists()
    for _ in range(2):
        result = service.update_profile(
            "Selected",
            {"truck_01": "iveco_sway_500"},
            175000,
        )
        assert result["cash"] == 175000
    assert [
        asdict(item)
        for item in selected.state_repository.list_transports()
        if item.status == "active"
    ] == before
    assert (
        project_vehicle(selected.get_vehicle("truck_01"))["model_id"]
        == "iveco_sway_500"
    )
    assert project_player(other_game._get_player()) == other_before
    selected.state_repository.save_player(
        PlayerState(**{**other_before, "cash": 12345})
    )
    service.update_profile(
        "Selected",
        {"truck_01": "iveco_sway_500"},
        None,
    )
    assert selected._get_player().cash == 12345
    with pytest.raises(ValueError):
        service.update_profile(
            "Selected",
            {"unknown": "iveco_sway_500"},
            1,
        )
    with pytest.raises(ValueError):
        service.update_profile(
            "Selected",
            {"truck_01": "mercedes_eactros_600"},
            1,
        )
    assert selected._get_player().cash == 12345


@pytest.fixture
def maintenance(database, runtime, game, catalogue, tmp_path):
    settings = replace(
        make_settings(tmp_path),
        db_path=database.path,
        vehicle_catalogue_path=catalogue.path,
    )
    accounts = AccountRepository(database)
    user = accounts.create_user("Selected", "test-hash")
    selected = build_player_service(runtime, user["id"])
    service = build_profile_maintenance_service(settings)
    return settings, service, selected, accounts


@pytest.mark.parametrize(
    "failure",
    [
        "negative",
        "float",
        "boolean",
        "unknown-user",
        "unknown-vehicle",
        "unknown-model",
        "empty",
        "uninitialized",
    ],
)
def test_maintenance_validation_preserves_state(maintenance, failure):
    _, service, selected, accounts = maintenance
    before = (
        [
            project_vehicle(item)
            for item in selected.state_repository.list_vehicles()
        ],
        project_player(selected._get_player()),
    )
    username = "Selected"
    assignments = {"truck_01": "man_tgx_520"}
    cash = None
    if failure in {"negative", "float", "boolean"}:
        cash = {"negative": -1, "float": 1.5, "boolean": True}[failure]
    if failure == "unknown-user":
        username = "Missing"
    if failure == "unknown-vehicle":
        assignments = {"missing": "man_tgx_520"}
    if failure == "unknown-model":
        assignments = {"truck_01": "missing"}
    if failure == "empty":
        assignments = {}
    if failure == "uninitialized":
        accounts.create_user("Empty", "test-hash")
        username = "Empty"
    with pytest.raises(ValueError):
        service.update_profile(username, assignments, cash)
    assert (
        [
            project_vehicle(item)
            for item in selected.state_repository.list_vehicles()
        ],
        project_player(selected._get_player()),
    ) == before


def test_maintenance_write_failure_rolls_back_and_retains_unselected(
    maintenance,
):
    _, service, selected, _ = maintenance
    vehicle = selected.state_repository.list_vehicles()[0]
    hamburg = selected.world.read().get_facility("hamburg_cta")
    vehicle.start_trip()
    vehicle.arrive(hamburg.location_snapshot())
    vehicle.start_trip()
    other = OwnedVehicle(
        "other",
        "Untouched",
        vehicle.mode,
        vehicle.capacity_tons,
        hamburg.facility_uid,
        "enroute",
        model_id=vehicle.model_id,
        operating_cost_eur_per_km=vehicle.operating_cost_eur_per_km,
        facility_uid=hamburg.facility_uid,
        location=hamburg.location_snapshot(),
    )
    vehicles = [project_vehicle(vehicle), project_vehicle(other)]
    selected.state_repository.save_vehicle(vehicle)
    selected.state_repository.save_vehicle(other)
    repository = selected.state_repository
    service.player_unit_of_work_factory = lambda user_id: selected.unit_of_work
    before = project_player(repository.get_player())
    with patch.object(
        repository,
        "save_player",
        side_effect=RuntimeError("disk write failed"),
    ):
        with pytest.raises(RuntimeError):
            service.update_profile(
                "Selected", {"truck_01": "man_tgx_520"}, 123
            )
    assert [
        project_vehicle(item) for item in repository.list_vehicles()
    ] == vehicles
    assert project_player(repository.get_player()) == before
    result = service.update_profile("selected", {"truck_01": "man_tgx_520"})
    after = [project_vehicle(item) for item in repository.list_vehicles()]
    assert after[1] == vehicles[1]
    assert (
        after[0]["status"] == "enroute"
        and after[0]["hub_id"] == hamburg.facility_uid
    )
    assert after[0]["id"] == "truck_01"
    assert (
        result["username"] == "Selected" and result["cash"] == before["cash"]
    )


def test_backup_reads_committed_wal_and_refuses_overwrite(tmp_path):
    source = tmp_path / "source.db"
    target = tmp_path / "backups" / "backup.db"
    with closing(sqlite3.connect(source)) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE sample (value TEXT)")
        writer.execute("INSERT INTO sample VALUES ('committed')")
        writer.commit()
        writer.execute("INSERT INTO sample VALUES ('uncommitted')")
        backup_database(source, target)
        with closing(sqlite3.connect(target)) as copy:
            assert copy.execute("SELECT value FROM sample").fetchall() == [
                ("committed",)
            ]
        with pytest.raises(FileExistsError):
            backup_database(source, target)
    source.rename(tmp_path / "closed.db")
    target.rename(tmp_path / "closed-backup.db")


@pytest.mark.parametrize(
    "values",
    [
        ["missing-equals"],
        ["a="],
        ["=b"],
        ["a=b=c"],
        ["a=b", "a=c"],
        ["a=b", " a = b "],
    ],
)
def test_cli_rejects_invalid_and_duplicate_assignments(values):
    with pytest.raises(ValueError):
        parse_assignments(values)
    assert parse_assignments([" a = model "]) == {"a": "model"}


@pytest.mark.parametrize("cash", [None, 12345])
def test_cli_backs_up_before_mutation_and_preserves_cash(
    maintenance, monkeypatch, capsys, cash
):
    settings, _, selected, _ = maintenance
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "maintenance",
            "--username",
            "Selected",
            "--vehicle",
            "truck_01=man_tgx_520",
        ],
    )
    if cash is not None:
        sys.argv.extend(["--cash", str(cash)])
    before = [
        project_vehicle(item)
        for item in selected.state_repository.list_vehicles()
    ]
    with patch(
        "scripts.update_test_profile.Settings.from_env", return_value=settings
    ):
        main()
    result = json.loads(capsys.readouterr().out)
    assert result["cash"] == (175000 if cash is None else cash)
    with closing(sqlite3.connect(result["backup"])) as db:
        stored = db.execute(
            "SELECT vehicle_id, model_id FROM owned_vehicles "
            "WHERE user_id = (SELECT id FROM users WHERE username='Selected')"
        ).fetchall()
    assert stored == [(item["id"], item["model_id"]) for item in before]
    assert [
        project_vehicle(item)
        for item in selected.state_repository.list_vehicles()
    ][0]["model_id"] == "man_tgx_520"


def test_cli_backup_failure_never_constructs_mutation_service(
    maintenance, monkeypatch
):
    settings, _, _, _ = maintenance
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "maintenance",
            "--username",
            "Selected",
            "--vehicle",
            "truck_01=man_tgx_520",
            "--cash",
            "100",
        ],
    )
    with (
        patch(
            "scripts.update_test_profile.Settings.from_env",
            return_value=settings,
        ),
        patch(
            "scripts.update_test_profile.backup_database",
            side_effect=OSError("backup failed"),
        ),
        patch(
            "scripts.update_test_profile.build_profile_maintenance_service"
        ) as build,
    ):
        with pytest.raises(OSError):
            main()
        build.assert_not_called()


def test_cli_argument_error_precedes_backup(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["maintenance", "--username", "Selected", "--vehicle", "broken"],
    )
    with patch("scripts.update_test_profile.backup_database") as backup:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
        backup.assert_not_called()


@pytest.mark.parametrize("limited_cash", [False, True])
async def test_dispatch_reprices_after_concurrent_profile_maintenance(
    maintenance, limited_cash
):
    _, service, game, _ = maintenance
    route_started = asyncio.Event()
    release_route = asyncio.Event()
    original_route = game.router.route

    async def delayed_route(*args):
        route_started.set()
        await release_route.wait()
        return await original_route(*args)

    game.router.route = delayed_route
    before = 285 if limited_cash else 175000
    player = project_player(game._get_player())
    game.state_repository.save_player(
        PlayerState(**{**player, "cash": before})
    )
    [project_contract(value) for value in game.refresh_market(force=True)]
    contract = first_berlin_contract(game)
    task = asyncio.create_task(game.dispatch(contract["id"], "truck_01"))
    await asyncio.wait_for(route_started.wait(), 2)
    try:
        service.update_profile("Selected", {"truck_01": "man_tgx_520"})
    finally:
        release_route.set()
    if limited_cash:
        with pytest.raises(ValueError, match="Nicht genug"):
            await task
        assert game.state_repository.list_transports() == ()
        assert game._get_player().cash == before
    else:
        trip = project_transport(await task)
        assert trip["operating_cost_eur"] == round(80 + 400 * 0.53)
        assert game._get_player().cash == before - trip["operating_cost_eur"]
