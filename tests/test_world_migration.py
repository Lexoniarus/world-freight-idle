"""Preserve existing economics, routes and profile identities during migration."""

import copy
import runpy
import sqlite3
import sys
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.bootstrap import build_world_state_migration_service, game_store
from app.domain.errors import WorldCatalogueError
from app.domain.game import OwnedVehicle
from app.repositories.world_state_migration import (
    WorldStateMigrationRepository,
)
from app.services.world_state_migration import (
    endpoint_snapshot,
    migrate_world_records,
    preserve_routing_endpoint,
)
from tests.test_api import make_settings
from tests.test_game import first_berlin_contract


def legacy_records():
    contract = {
        "id": "keep-contract",
        "origin_hub_id": "berlin_westhafen",
        "destination_hub_id": "hamburg_cta",
        "cargo": "Stückgut",
        "tons": 10,
    }
    trip = {
        "id": "keep-trip",
        "vehicle_id": "keep-truck",
        "contract": contract,
        "origin": {
            "lat": 52.5367,
            "lon": 13.3407,
            "address": "historical origin",
        },
        "destination": {
            "lat": 53.5083,
            "lon": 9.9286,
            "address": "historical destination",
        },
        "route_geojson": {
            "type": "LineString",
            "coordinates": [[13.3407, 52.5367], [9.9286, 53.5083]],
        },
        "departed_at": 1,
        "arrives_at": 2,
        "payout_eur": 333,
        "operating_cost_eur": 111,
    }
    return {
        "user:alice:player": {"cash": 1234},
        "user:alice:vehicles": [
            {
                "id": "keep-truck",
                "hub_id": "berlin_westhafen",
                "status": "enroute",
            }
        ],
        "user:alice:contracts": [contract],
        "user:alice:active_trips": [trip],
        "user:bob:player": {"cash": 9876},
        "user:bob:vehicles": [],
        "active_trip": None,
    }


def test_world_migration_preserves_snapshots_and_rejects_unknown_endpoints(
    world_catalogue,
):
    world = world_catalogue.read()
    before = legacy_records()
    saved = copy.deepcopy(before)
    after = migrate_world_records(before, world)
    assert before == saved
    with pytest.raises(ValueError, match="version"):
        migrate_world_records({"world_state_version": 2}, world)
    assert after["user:alice:player"] == before["user:alice:player"]
    assert after["user:bob:player"] == before["user:bob:player"]
    trip = after["user:alice:active_trips"][0]
    for key in (
        "id",
        "origin",
        "destination",
        "route_geojson",
        "arrives_at",
        "departed_at",
        "payout_eur",
        "operating_cost_eur",
    ):
        assert trip[key] == before["user:alice:active_trips"][0][key]
    assert trip["destination_snapshot"]["lat"] == trip["destination"]["lat"]
    assert (
        trip["destination_snapshot"]["geocoding_status"]
        == "legacy_transport_snapshot"
    )
    assert after["user:alice:world_state_version"] == 1
    assert migrate_world_records(after, world) == after
    # An already snapshotted game no longer needs deleted catalogue records.
    assert migrate_world_records(after, replace(world, facilities=())) == after
    before["user:bob:vehicles"] = [{"hub_id": "unknown"}]
    with pytest.raises(KeyError):
        migrate_world_records(before, world)
    estimated = next(
        facility
        for facility in world.facilities
        if not facility.has_verified_location()
    )
    assert (
        endpoint_snapshot(estimated.facility_uid, world)["geocoding_status"]
        == "estimated_for_simulation"
    )
    unroutable = replace(estimated, coordinate_evidence=())
    with pytest.raises(ValueError):
        endpoint_snapshot(
            unroutable.facility_uid,
            replace(world, facilities=(unroutable,)),
        )
    endpoint = world.get_facility("berlin_westhafen").to_dict()
    assert preserve_routing_endpoint(endpoint, None) == endpoint
    assert preserve_routing_endpoint(endpoint, endpoint)["coordinate_evidence"]
    assert migrate_world_records(
        {"active_trip": saved["user:alice:active_trips"][0]}, world
    )["active_trip"]["origin_snapshot"]


def test_world_migration_repository_rolls_back_and_cli_requires_backup(
    store, tmp_path, world_catalogue, monkeypatch
):
    settings = replace(
        make_settings(tmp_path),
        db_path=store.path,
        world_catalogue_path=world_catalogue.path,
    )
    for key, value in legacy_records().items():
        store.set_json(key, value)
    service = build_world_state_migration_service(settings)
    original = store.get_json("user:alice:vehicles")
    store.set_json("user:bob:vehicles", [{"hub_id": "unknown"}])
    with pytest.raises(KeyError):
        service.migrate()
    assert store.get_json("user:alice:vehicles") == original
    store.set_json("user:bob:vehicles", [])
    backup = tmp_path / "players-backup.sqlite3"
    script = (
        Path(__file__).resolve().parents[1] / "scripts/migrate_world_state.py"
    )
    monkeypatch.setattr(sys, "argv", ["migrate", "--backup", str(backup)])
    with patch("app.config.Settings.from_env", return_value=settings):
        runpy.run_path(str(script), run_name="__main__")
        with patch(
            "app.bootstrap.build_world_state_migration_service"
        ) as build:
            with pytest.raises(FileExistsError):
                runpy.run_path(str(script), run_name="__main__")
            build.assert_not_called()
    assert service.migrate() == 0
    with closing(sqlite3.connect(backup)) as connection:
        assert (
            connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        )
    repository = WorldStateMigrationRepository(store.path)
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute(
            "CREATE TRIGGER fail_write BEFORE INSERT ON kv WHEN NEW.key='fail' BEGIN SELECT RAISE(ABORT, 'write failed'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        repository.transform(
            lambda records: {**records, "first": 1, "fail": 2}
        )
    assert store.get_json("first") is None


async def test_snapshot_routing_and_settlement_survive_catalogue_failure(game):
    contract = first_berlin_contract(game)
    original = game.router.route
    game.router.route = AsyncMock(side_effect=original)
    with patch.object(
        game.world, "read", side_effect=WorldCatalogueError("offline")
    ):
        quote = await game.quote_contract(contract["id"])
        game.router.route.assert_awaited_once_with(
            contract["origin"]["lat"],
            contract["origin"]["lon"],
            contract["destination"]["lat"],
            contract["destination"]["lon"],
        )
        trip = await game.dispatch(contract["id"], "truck_01")
        cash = game_store(game).get_json("player")["cash"]
        trip["departed_at"] = 0
        trip["arrives_at"] = 1
        game_store(game).set_json("active_trips", [trip])
        assert game.reconcile_arrival()
        assert (
            game_store(game).get_json("player")["cash"]
            == cash + trip["payout_eur"]
        )
        assert not game.reconcile_arrival()
        assert game.list_vehicles()[0]["hub"] == trip["destination_snapshot"]
        with pytest.raises(WorldCatalogueError):
            game.refresh_market(force=True)
        expired = game_store(game).get_json("contracts")
        for item in expired:
            item["expires_at"] = 0
        game_store(game).set_json("contracts", expired)
        assert game.refresh_market() == []
        assert game.state()["vehicles"]
    assert quote["origin"] == contract["origin"]


def test_legacy_projections_require_explicit_aliases(game):
    legacy = OwnedVehicle.from_dict(
        {
            "id": "legacy",
            "name": "Legacy",
            "mode": "truck",
            "capacity_tons": 12,
            "hub_id": "berlin_westhafen",
            "status": "idle",
        }
    )
    expanded = game._expand_vehicle(legacy)
    assert expanded["hub"]["facility_uid"]
    assert legacy.hub_id == "berlin_westhafen"

    contract = {
        "origin_hub_id": "berlin_westhafen",
        "destination_hub_id": "hamburg_cta",
    }
    expanded = game._expand_contract(contract)
    assert (
        expanded["origin"]["facility_uid"]
        != expanded["destination"]["facility_uid"]
    )

    unknown = OwnedVehicle.from_dict(
        {
            "id": "unknown",
            "name": "Unknown",
            "mode": "truck",
            "capacity_tons": 12,
            "hub_id": "unknown",
            "status": "idle",
        }
    )
    with pytest.raises(KeyError):
        game._expand_vehicle(unknown)


async def test_runtime_never_geocodes_facilities(game):
    from app.services.map_locations import MapLocationService

    with patch(
        "app.providers.geocoding.NominatimGeocoder.geocode",
        side_effect=AssertionError("runtime geocoder forbidden"),
    ) as geocode:
        assert await MapLocationService(game.world).list_hubs()
        contract = first_berlin_contract(game)
        await game.quote_contract(contract["id"])
        await game.dispatch(contract["id"], "truck_01")
        geocode.assert_not_awaited()
