"""Offline import: preserved history, isolated owners and fail-closed writes."""

import copy
import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_transport,
    project_vehicle,
)
from app.bootstrap import (
    GameRuntime,
    build_game_importer,
    build_player_service,
)
from app.config import Settings
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.errors import PersistenceError
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.world_scopes import WorldScope
from app.repositories.database_backup import backup_database
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameStateRepository
from app.repositories.legacy_game_import import (
    LegacyGameImporter,
    read_legacy_json,
)
from app.repositories.legacy_import_mapping import read_legacy_profile
from app.services.auth import PasswordHasher


@pytest.fixture
def legacy_source(tmp_path, game):
    now = game.now()
    vehicle = game.state_repository.list_vehicles()[0]
    offer = next(
        o
        for o in game.state_repository.list_offers()
        if o.origin.facility_uid == vehicle.facility_uid
        and o.tons <= vehicle.capacity_tons
    )
    offer = replace(
        offer,
        created_at=now - 500,
        expires_at=now + 500,
        market_model="nhm_v1",
        market_context=None,
        payload_band="heavy",
    )
    trip = ActiveTransport(
        "trip-1",
        vehicle.id,
        HistoricalContractSnapshot.from_offer(offer),
        offer.origin,
        offer.destination,
        RouteSnapshot(
            ((13.0, 52.0), (14.0, 53.0)), 100, 120, "saved-provider"
        ),
        now - 120,
        now - 1,
        987,
        142,
        journey=unmetered_journey(
            100,
            (now - 1) - (now - 120),
        ),
    )
    vehicle.start_trip()
    expired = replace(
        offer, id="expired", created_at=now - 2000, expires_at=now - 1000
    )
    state = {
        "player": {"cash": 123456, "completed": 37, "reputation": 41},
        "vehicles": [legacy_vehicle_projection(vehicle)],
        "contracts": [project_contract(offer), project_contract(expired)],
        "active_trips": [legacy_transport_projection(trip)],
    }
    password_hash = PasswordHasher().hash_password("fixture-password-42")
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,password_hash TEXT,created_at REAL);
CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE sessions(token_hash TEXT,user_id TEXT,expires_at REAL);
CREATE TABLE route_cache(cache_key TEXT,payload TEXT,updated_at REAL);
""")
        for uid in ("a", "b", "c"):
            connection.execute(
                "INSERT INTO users VALUES (?,?,?,?)",
                (uid, "User_" + uid, password_hash, 100),
            )
            connection.executemany(
                "INSERT INTO kv VALUES (?,?)",
                [
                    (f"user:{uid}:{key}", json.dumps(value))
                    for key, value in state.items()
                ],
            )
        connection.execute(
            "INSERT INTO sessions VALUES ('old-session','a',9999999999)"
        )
        connection.commit()
    importer = LegacyGameImporter(
        path,
        WorldScope(game.world.read()),
        "nhm_v1",
        game.catalogue.list_models(),
    )
    return path, importer, state, now, password_hash


def update_legacy(path, key, value):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE kv SET value=? WHERE key=?", (json.dumps(value), key)
        )
        connection.commit()


def without_city_uids(value):
    if isinstance(value, dict):
        return {
            k: without_city_uids(v)
            for k, v in value.items()
            if k != "city_uid"
        }
    if isinstance(value, list):
        return [without_city_uids(v) for v in value]
    return value


def test_offline_import_preserves_profiles_history_and_settles_once(
    legacy_source, tmp_path, game
):
    path, importer, state, now, password_hash = legacy_source
    original = path.read_bytes()
    report = importer.inspect(now)
    assert (
        report.accounts,
        report.vehicles,
        report.offers,
        report.transports,
    ) == (3, 3, 3, 3)
    assert {e.contract_id for e in report.excluded_offers} == {"expired"}
    backup = tmp_path / "backup.db"
    target = tmp_path / "target.db"
    backup_database(path, backup)
    importer = LegacyGameImporter(
        backup,
        importer.reader.world,
        importer.market_model,
        tuple(importer.reader.models.values()),
    )
    assert importer.import_to(target, now) == report
    database = SqliteGameDatabase(target)
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT id,username,password_hash,created_at FROM users ORDER BY id"
        ).fetchall()
        assert [tuple(r) for r in rows] == [
            (uid, "User_" + uid, password_hash, 100) for uid in ("a", "b", "c")
        ]
        assert PasswordHasher().verify_password(
            "fixture-password-42", rows[0]["password_hash"]
        )
        assert not PasswordHasher().verify_password(
            "wrong", rows[0]["password_hash"]
        )
        tables = {
            r[0]
            for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert not {"sessions", "route_cache", "kv"} & tables
    for uid in ("a", "b", "c"):
        repository = SqliteGameStateRepository(database, uid)
        player = repository.get_player()
        assert player is not None
        assert player.cash == 123456
        assert player.completed == 37
        trip = repository.list_transports()[0]
        assert trip.status == "active" and trip.is_due(now)
        assert without_city_uids(
            legacy_transport_projection(trip)
        ) == without_city_uids(state["active_trips"][0])
        assert without_city_uids(
            legacy_vehicle_projection(repository.list_vehicles()[0])
        ) == without_city_uids(state["vehicles"][0])
    runtime = GameRuntime(
        database,
        game.world,
        game.router,
        game.market,
        game.catalogue,
        game.market_scope,
        1,
    )
    service = build_player_service(runtime, "a")
    assert service.reconcile_arrival()
    assert not service.reconcile_arrival()
    settled_player = service.state_repository.get_player()
    other_player = SqliteGameStateRepository(database, "b").get_player()
    assert settled_player is not None and other_player is not None
    assert settled_player.cash == 124443
    assert settled_player.completed == 38
    assert other_player.cash == 123456
    assert path.read_bytes() == original
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        importer.import_to(target, now)
    assert target.read_bytes() == before
    with pytest.raises(FileExistsError):
        importer.import_to(backup, now)


def test_offline_import_rejects_corruption_and_unknown_state(
    legacy_source, tmp_path
):
    path, importer, state, now, _ = legacy_source
    for values in (
        {**state["player"], "cash": -1},
        {**state["player"], "cash": True},
        {**state["player"], "unknown": 1},
    ):
        update_legacy(path, "user:a:player", values)
        with pytest.raises(PersistenceError):
            importer.import_to(tmp_path / "invalid.db", now)
        assert not (tmp_path / "invalid.db").exists()
    update_legacy(path, "user:a:player", state["player"])
    for key, value in (
        ("vehicles", state["vehicles"] * 2),
        ("vehicles", [{**state["vehicles"][0], "id": "missing"}]),
        ("vehicles", [{**state["vehicles"][0], "capacity_tons": 0.01}]),
        (
            "vehicles",
            [
                {
                    **state["vehicles"][0],
                    "facility_uid": state["contracts"][0][
                        "destination_facility_uid"
                    ],
                    "hub_id": state["contracts"][0]["destination_hub_id"],
                    "location_snapshot": state["contracts"][0]["destination"],
                }
            ],
        ),
        ("vehicles", [{**state["vehicles"][0], "status": "idle"}]),
        ("active_trips", []),
        ("active_trips", state["active_trips"] * 2),
        ("contracts", [{**state["contracts"][0], "tons": float("nan")}]),
    ):
        update_legacy(path, "user:a:" + key, value)
        with pytest.raises(PersistenceError):
            importer.inspect(now)
        update_legacy(path, "user:a:" + key, state[key])
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("INSERT INTO kv VALUES ('unassigned','{}')")
        connection.commit()
    with pytest.raises(PersistenceError):
        importer.inspect(now)
    with pytest.raises(ValueError):
        read_legacy_json([("key", 1), ("key", 2)])
    assert read_legacy_json([("key", 1)]) == {"key": 1}


def test_import_rejects_unknown_tables_and_failed_integrity(legacy_source):
    from unittest.mock import MagicMock

    path, importer, _, now, _ = legacy_source
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("CREATE TABLE unknown(value TEXT)")
    with pytest.raises(PersistenceError):
        importer.inspect(now)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("DROP TABLE unknown")
    original = path.read_bytes()
    with closing(sqlite3.connect(path)) as real:
        connection = MagicMock(wraps=real)

        def execute(sql, *args):
            if sql == "PRAGMA integrity_check":
                result = MagicMock()
                result.fetchall.return_value = [("damaged index",)]
                return result
            return real.execute(sql, *args)

        connection.execute.side_effect = execute
        with patch(
            "app.repositories.legacy_game_import.sqlite3.connect",
            return_value=connection,
        ):
            with pytest.raises(PersistenceError):
                importer.inspect(now)
        connection.close.assert_called_once()
    assert path.read_bytes() == original


def test_legacy_snapshot_decoding_rejects_conflicting_facts(legacy_source):
    _, importer, state, _, _ = legacy_source
    reader = importer.reader
    for loader, value in (
        (reader.location, state["contracts"][0]["origin"]),
        (reader.offer, state["contracts"][0]),
        (reader.vehicle, state["vehicles"][0]),
        (reader.transport, state["active_trips"][0]),
    ):
        with pytest.raises(ValueError):
            loader({**value, "unknown_field": 1})
    original = state["contracts"][0]
    for key, value in (
        ("cargo_code", "unknown"),
        ("cargo", "Changed"),
        ("origin_hub_id", "unknown"),
        ("origin_facility_uid", "unknown"),
        ("cargo_evidence", {}),
    ):
        with pytest.raises((ValueError, KeyError)):
            reader.offer({**original, key: value})
    for key, value in (
        ("id", "other"),
        ("company_uid", "other"),
        ("lat", None),
        ("lon", 200),
    ):
        with pytest.raises(ValueError):
            reader.location({**original["origin"], key: value})
    with pytest.raises(ValueError):
        reader.vehicle({**state["vehicles"][0], "facility_uid": "other"})
    for key, value in (
        ("profit_eur", 0),
        ("origin_snapshot", {}),
        ("route_geojson", {"type": "Point"}),
    ):
        with pytest.raises(ValueError):
            reader.transport({**state["active_trips"][0], key: value})
    with pytest.raises(ValueError):
        read_legacy_profile(
            {**original["origin_cargo_evidence"], "confidence": 2}
        )
    feature = copy.deepcopy(state["active_trips"][0])
    feature["route_geojson"] = {
        "type": "Feature",
        "geometry": feature["route_geojson"],
    }
    assert reader.transport(feature) == reader.transport(
        state["active_trips"][0]
    )


def test_import_rolls_back_reconciliation_and_write_failures(
    legacy_source, tmp_path
):
    path, importer, _, now, _ = legacy_source
    original = path.read_bytes()
    target = tmp_path / "failed.db"
    for hook in (
        "app.repositories.legacy_game_import.reconcile_import",
        "app.repositories.game_state.SqliteGameStateRepository.save_transport",
    ):
        with patch(hook, side_effect=PersistenceError("simulated")):
            with pytest.raises(PersistenceError):
                importer.import_to(target, now)
        assert not target.exists()
        assert path.read_bytes() == original


def test_import_cli_requires_backup_and_separate_paths(
    legacy_source, tmp_path, monkeypatch, capsys
):
    from scripts import import_legacy_game as cli

    path, importer, _, now, _ = legacy_source
    monkeypatch.setattr(
        cli,
        "build_game_importer",
        lambda source, settings, exclude_global_demo=False: importer,
    )
    monkeypatch.setattr(cli.time, "time", lambda: now)
    monkeypatch.setattr(
        "sys.argv", ["import", "--source", str(path), "--check"]
    )
    cli.main()
    assert '"accounts": 3' in capsys.readouterr().out
    backup = tmp_path / "backup.db"
    output = tmp_path / "output.db"
    monkeypatch.setattr(
        "sys.argv",
        [
            "import",
            "--source",
            str(path),
            "--backup",
            str(backup),
            "--output",
            str(output),
        ],
    )
    with patch.object(cli, "backup_database", side_effect=OSError("disk")):
        with pytest.raises(OSError):
            cli.main()
    assert not output.exists()
    cli.main()
    assert backup.exists() and output.exists()
    with pytest.raises(SystemExit):
        cli.main()
    for extra in (
        [],
        ["--backup", str(path), "--output", str(tmp_path / "other.db")],
        ["--check", "--backup", str(backup)],
    ):
        monkeypatch.setattr(
            "sys.argv", ["import", "--source", str(path), *extra]
        )
        with pytest.raises(SystemExit):
            cli.main()
    settings = Settings.from_env()
    built = build_game_importer(path, settings)
    assert built.inspect(now).accounts == 3
    with pytest.raises(PersistenceError):
        build_game_importer(tmp_path / "missing.db", settings).inspect(now)


def test_import_reconciliation_detects_retained_value_changes(
    legacy_source, tmp_path
):
    from app.repositories.legacy_game_import import reconcile_import

    _, importer, _, now, _ = legacy_source
    target = tmp_path / "reconcile.db"
    importer.import_to(target, now)
    database = SqliteGameDatabase(target)
    profiles = importer._read_profiles(now)
    reconcile_import(database, profiles)
    for statement in (
        "UPDATE users SET created_at=101 WHERE id='a'",
        "UPDATE player_states SET cash=cash+1 WHERE user_id='a'",
        "UPDATE owned_vehicles SET name='changed' WHERE user_id='a'",
    ):
        with pytest.raises(PersistenceError):
            with database.transaction():
                with database.connect() as connection:
                    connection.execute(statement)
                reconcile_import(database, profiles)
        reconcile_import(database, profiles)

    with database.connect() as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "CREATE TABLE corrupt_link(owner TEXT REFERENCES users(id))"
        )
        connection.execute("INSERT INTO corrupt_link VALUES('unknown')")
    with pytest.raises(PersistenceError, match="integrity check failed"):
        reconcile_import(database, profiles)


def test_backup_failure_removes_only_its_own_incomplete_output(tmp_path):
    from unittest.mock import MagicMock

    source = tmp_path / "source.db"
    target = tmp_path / "incomplete.db"
    source.write_bytes(b"source untouched")
    with patch("app.repositories.database_backup.sqlite3.connect") as connect:
        origin = MagicMock()
        destination = MagicMock()
        connect.side_effect = [origin, destination]
        origin.backup.side_effect = sqlite3.OperationalError("disk full")
        with pytest.raises(sqlite3.OperationalError):
            backup_database(source, target)
        assert not target.exists()
        origin.close.assert_called_once()
        destination.close.assert_called_once()
    assert source.read_bytes() == b"source untouched"


def test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values(
    game,
):
    from dataclasses import asdict

    from app.domain.cargo import DocumentedCargo
    from app.repositories.snapshot_mapping import (
        load_documented_cargo,
        load_historical_contract,
    )

    offer = game.state_repository.list_offers()[0]
    saved = HistoricalContractSnapshot.from_offer(offer)
    assert load_historical_contract(asdict(saved)) == saved
    goods = DocumentedCargo("10", "Metals", "output", True, "official", None)
    old = replace(
        saved,
        cargo=goods,
        origin_cargo_evidence=None,
        destination_cargo_evidence=None,
        market_model=None,
        cargo_system=None,
        trade_match_type=None,
    )
    assert load_historical_contract(asdict(old)) == old
    assert load_documented_cargo(asdict(goods)) == goods
    for changes in ({"role": "unknown"}, {"standard": 1}, {"code": ""}):
        with pytest.raises(ValueError):
            replace(goods, **changes)
    for changes in (
        {"id": ""},
        {"tons": float("inf")},
        {"expires_at": saved.created_at},
        {"destination": saved.origin},
        {"origin_cargo_evidence": None},
        {"cargo": replace(saved.cargo, code="other")},
    ):
        with pytest.raises(ValueError):
            replace(saved, **changes)
    with pytest.raises(ValueError):
        replace(old, origin_cargo_evidence=saved.origin_cargo_evidence)
    with pytest.raises(KeyError):
        load_historical_contract({})
    with pytest.raises(TypeError):
        load_documented_cargo({"source": None})


def test_old_reference_documents_and_retired_offers_are_explicitly_handled(
    legacy_source,
):
    from dataclasses import asdict

    from app.repositories.legacy_import_mapping import read_documented_cargo
    from app.repositories.snapshot_mapping import load_location

    _, importer, state, _, _ = legacy_source
    reader = importer.reader
    goods = {
        "code": "10",
        "name": "Metals",
        "role": "output",
        "standard": True,
        "evidence_type": "official",
        "source": {
            "url": "https://example.test/fact",
            "role": "official",
            "verified_at": "2026-09-18",
        },
    }
    offer = copy.deepcopy(state["contracts"][0])
    for key in (
        "market_model",
        "cargo_system",
        "origin_cargo_evidence",
        "destination_cargo_evidence",
        "trade_match_type",
    ):
        offer.pop(key)
    offer.update(cargo="Metals", cargo_code="10", cargo_evidence=goods)
    path, _, _, now, _ = legacy_source
    update_legacy(path, "user:a:contracts", [offer])
    report = importer.inspect(now)
    assert any(
        item.user_id == "a" and item.reason == "obsolete_goods_model"
        for item in report.excluded_offers
    )
    offer["origin"]["cargo"] = [
        goods,
        state["contracts"][0]["origin_cargo_evidence"],
    ]
    offer["origin"].pop("location_verified")
    old = reader.historical_contract(offer)
    assert old.market_model is None and old.cargo.name == "Metals"
    assert load_location(asdict(old.origin)) == old.origin
    assert len(old.origin.handling_evidence) == 2
    compact = copy.deepcopy(offer["origin"])
    compact.pop("company")
    partial = reader.location(compact)
    assert partial.company.company_uid == compact["company_uid"]
    assert partial.company.legal_name is None
    assert load_location(asdict(partial)) == partial
    no_company = {**compact, "company_uid": None, "lat": None, "lon": None}
    assert reader.location(no_company).company is None
    vehicle = {**state["vehicles"][0]}
    vehicle.pop("location_snapshot")
    assert reader.vehicle(vehicle).location is not None
    with pytest.raises(ValueError):
        reader.location({**compact, "snapshot_version": 99})
    with pytest.raises(ValueError):
        reader.historical_contract({**offer, "cargo_code": "wrong"})
    with pytest.raises(ValueError):
        read_documented_cargo({**goods, "role": "bad"})
    for changed in (
        {**offer, "tons": -1},
        {**offer, "expires_at": offer["created_at"]},
        {**offer, "destination": offer["origin"]},
        {**offer, "origin_hub_id": "other"},
    ):
        with pytest.raises(ValueError):
            reader.validate_obsolete_offer(changed)


def test_global_demo_exclusion_requires_explicit_choice(
    legacy_source, tmp_path
):
    path, importer, state, now, _ = legacy_source
    demo = copy.deepcopy(state)
    demo["active_trips"] = []
    demo["vehicles"][0]["status"] = "idle"
    demo["contracts"] = []
    with closing(sqlite3.connect(path)) as connection:
        connection.executemany(
            "INSERT INTO kv VALUES (?,?)",
            [(key, json.dumps(value)) for key, value in demo.items()],
        )
        connection.execute("INSERT INTO kv VALUES ('world_state_version','1')")
        connection.execute(
            "INSERT INTO kv VALUES ('user:a:world_state_version','1')"
        )
        connection.commit()
    with pytest.raises(PersistenceError):
        importer.inspect(now)
    explicit = LegacyGameImporter(
        path,
        importer.reader.world,
        importer.market_model,
        tuple(importer.reader.models.values()),
        exclude_global_demo=True,
    )
    assert explicit.inspect(now).accounts == 3
    obsolete = copy.deepcopy(state["contracts"][0])
    obsolete.pop("market_model")
    update_legacy(path, "contracts", [obsolete])
    assert explicit.inspect(now).accounts == 3
    explicit.import_to(tmp_path / "selected.db", now)
    update_legacy(path, "active_trips", state["active_trips"])
    with pytest.raises(PersistenceError):
        explicit.inspect(now)
    update_legacy(path, "active_trips", [])
    update_legacy(path, "world_state_version", 2)
    with pytest.raises(PersistenceError):
        explicit.inspect(now)
    update_legacy(path, "world_state_version", 1)
    update_legacy(path, "user:a:world_state_version", 2)
    with pytest.raises(PersistenceError):
        explicit.inspect(now)


def legacy_vehicle_projection(vehicle):
    """Build only pre-energy fields for the explicit old-format fixture."""
    return {
        key: value
        for key, value in project_vehicle(vehicle).items()
        if key not in {"energy", "energy_level", "top_speed_kmh"}
    }


def legacy_transport_projection(trip):
    """Build the pre-energy transport contract, excluding new projections."""
    return {
        key: value
        for key, value in project_transport(trip).items()
        if key
        not in {
            "journey",
            "progress",
            "start",
            "approach_distance_km",
            "delivery_distance_km",
            "route_legs",
        }
    }
