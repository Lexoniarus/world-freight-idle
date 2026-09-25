"""Private scalar analytics, historical dimensions and UTC boundaries."""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_current_user, get_game_service
from app.bootstrap import build_analytics_service
from app.domain.errors import PersistenceError
from app.main import create_app
from app.repositories.analytics import SqliteAnalyticsReader
from app.services.analytics import AnalyticsService, summarize, validate_scope
from tests.test_api import make_settings, make_static_files

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC).timestamp()


def insert_trip(
    database,
    vehicle_id,
    identifier="t1",
    arrival=NOW - 1,
    v2=True,
    status="settled",
    change=None,
):
    payload = {
        "kind": "transport",
        "version": 2,
        "data": {
            "origin": {"city": {"city_uid": "city-a", "name": "Same name"}},
            "route": {"distance_km": 150.0, "coordinates": [[13, 52]] * 2000},
            "contract": {
                "tons": 4.5,
                "market_model": "nhm_v2" if v2 else "nhm_v1",
                "market_context": {
                    "transport_class": "general",
                    "distance_band": "short",
                }
                if v2
                else None,
            },
        },
    }
    if change:
        change(payload)
    with database.connect() as db:
        db.execute(
            "INSERT INTO transports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "test-owner",
                identifier,
                vehicle_id,
                "c1",
                "origin",
                "destination",
                status,
                arrival - 600,
                arrival,
                arrival if status == "settled" else None,
                120,
                100,
                json.dumps(payload),
            ),
        )


def test_analytics_scalars_do_not_hydrate_routes(game, database, monkeypatch):
    vehicle = game.state_repository.list_vehicles()[0]
    insert_trip(database, vehicle.id)
    insert_trip(database, vehicle.id, "t2", NOW - 86400, v2=False)
    insert_trip(database, vehicle.id, "active", NOW + 86400, status="active")

    def forbidden(*args, **kwargs):
        pytest.fail("Analytics must not hydrate a transport or route")

    monkeypatch.setattr(
        "app.repositories.game_state.load_transport_record", forbidden
    )
    monkeypatch.setattr(
        "app.repositories.transport_mapping.load_transport", forbidden
    )
    monkeypatch.setattr(
        "app.domain.transports.RouteSnapshot.__init__", forbidden
    )
    monkeypatch.setattr(
        "app.domain.transports.ActiveTransport.__init__", forbidden
    )
    with database.connect() as db:
        before = db.total_changes
    reader = SqliteAnalyticsReader(database, "test-owner")
    facts = reader.read(NOW)
    assert all(
        not isinstance(value, (list, dict))
        for row in facts.history
        for value in row.values()
    )
    assert "coordinates" not in str(facts.history)
    assert len(facts.ongoing) == 1
    for days in ("7", "30", "90", "all"):
        data = AnalyticsService(reader).analyze(NOW, days, "company", None)
        assert data["totals"]["profit_eur"] == -40
        assert data["totals"]["tons"] == 9
        assert data["totals"]["distance_km"] == 300
        assert len(data["daily"]) == (2 if days == "all" else int(days))
        assert data["daily"][-1]["completed_transports"] == 1
        assert data["coverage"]["unclassified_transports"] == 1
        assert data["status"]["active_transports"] == 1
    for scope, scope_id, count in (
        ("city", "city-a", 2),
        ("vehicle", vehicle.id, 2),
        ("transport_class", "general", 1),
        ("distance_band", "short", 1),
        ("city", "other-owner-city", 0),
    ):
        data = AnalyticsService(reader).analyze(NOW, "all", scope, scope_id)
        assert data["totals"]["completed_transports"] == count
    assert summarize([])["revenue_per_km"] is None
    with database.connect() as db:
        assert db.total_changes == before
        assert db.execute("SELECT COUNT(*) FROM transports").fetchone()[0] == 3
    with pytest.raises(PersistenceError):
        SqliteAnalyticsReader(database, "unknown-account").read(NOW)


@pytest.mark.parametrize(
    "days,scope,scope_id",
    [
        ("1", "company", None),
        ("30", "model", "m"),
        ("30", "company", "x"),
        ("30", "city", None),
        ("30", "transport_class", "bogus"),
        ("30", "distance_band", "bogus"),
    ],
)
def test_analytics_scope_validation(days, scope, scope_id):
    with pytest.raises(ValueError):
        validate_scope(days, scope, scope_id)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(version=1),
        lambda p: p.update(version=True),
        lambda p: p.update(kind="offer"),
        lambda p: p["data"]["contract"].update(tons=True),
        lambda p: p["data"]["route"].update(distance_km=-1),
        lambda p: p["data"]["origin"]["city"].update(city_uid=None),
        lambda p: p["data"]["contract"]["market_context"].update(
            distance_band="bad"
        ),
    ],
)
def test_analytics_rejects_corrupt_scalar_fields(game, database, change):
    insert_trip(
        database, game.state_repository.list_vehicles()[0].id, change=change
    )
    with pytest.raises(PersistenceError):
        SqliteAnalyticsReader(database, "test-owner").read(NOW)


def test_analytics_empty_and_utc_boundary(game, database):
    reader = SqliteAnalyticsReader(database, "test-owner")
    data = AnalyticsService(reader).analyze(NOW, "all", "company", None)
    assert data["daily"] == []
    assert data["totals"]["completed_transports"] == 0
    start = datetime(2026, 9, 19, tzinfo=UTC).timestamp()
    vehicle = game.state_repository.list_vehicles()[0]
    insert_trip(database, vehicle.id, "before", start - 1)
    insert_trip(database, vehicle.id, "boundary", start)
    data = AnalyticsService(reader).analyze(NOW, "7", "company", None)
    assert data["totals"]["completed_transports"] == 2
    assert data["period_totals"]["completed_transports"] == 1
    assert data["daily"][0]["completed_transports"] == 1
    assert data["daily"][-1]["completed_transports"] == 0


@pytest.mark.asyncio
async def test_analytics_offline_arrival_is_idempotent(
    tmp_path, game, runtime
):
    choice = next(
        item
        for item in game.contract_choices(game.list_contracts())
        if item.eligible_vehicle_ids
    )
    trip = await game.dispatch(choice.offer.id, choice.eligible_vehicle_ids[0])
    game.now = lambda: trip.arrives_at + 1
    make_static_files(tmp_path)
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as client:
        application.state.game = runtime
        application.dependency_overrides[get_game_service] = lambda: game
        application.dependency_overrides[get_current_user] = lambda: {
            "id": "test-owner"
        }
        first = client.get("/api/v1/company/analytics?days=all").json()
        second = client.get("/api/v1/company/analytics?days=all").json()
        assert first == second
        assert first["status"]["completed"] == 1
        assert first["totals"]["revenue_eur"] == trip.payout_eur
        assert first["totals"]["distance_km"] == trip.route.distance_km
        assert first["status"]["idle_vehicles"] == 1


def test_analytics_is_read_only_and_account_scoped(
    game, database, monkeypatch
):
    from contextlib import contextmanager

    vehicle = game.state_repository.list_vehicles()[0]
    insert_trip(database, vehicle.id)
    with database.connect() as db:
        db.execute("INSERT INTO users VALUES ('second', 'Second', 'test', 0)")
        db.execute("INSERT INTO player_states VALUES ('second', 999, 42, 0)")
        columns = [
            row[1] for row in db.execute("PRAGMA table_info(owned_vehicles)")
        ][1:]
        names = ",".join(columns)
        db.execute(
            f"INSERT INTO owned_vehicles SELECT 'second', {names} FROM owned_vehicles WHERE user_id='test-owner'"
        )
        columns = [
            row[1] for row in db.execute("PRAGMA table_info(transports)")
        ][1:]
        names = ",".join(columns)
        db.execute(
            f"INSERT INTO transports SELECT 'second', {names} FROM transports WHERE user_id='test-owner'"
        )
    connect = database.connect

    @contextmanager
    def read_only_connection():
        with connect() as db:
            db.execute("PRAGMA query_only=ON")
            yield db

    monkeypatch.setattr(database, "connect", read_only_connection)
    first = AnalyticsService(
        SqliteAnalyticsReader(database, "test-owner")
    ).analyze(NOW, "all", "company", None)
    second = AnalyticsService(
        SqliteAnalyticsReader(database, "second")
    ).analyze(NOW, "all", "vehicle", vehicle.id)
    assert first["totals"]["completed_transports"] == 1
    assert second["totals"]["completed_transports"] == 1
    assert first["status"]["cash"] == 175000
    assert second["status"]["cash"] == 999
    assert second["coverage"]["progress_completed"] == 42
    assert second["coverage"]["recorded_transports"] == 1


def test_analytics_and_exact_api_require_session(tmp_path, game, runtime):
    make_static_files(tmp_path)
    application = create_app(make_settings(tmp_path))
    with TestClient(application) as client:
        for path in (
            "company/analytics",
            "map/facilities/berlin_westhafen",
            "map/cities/unknown",
        ):
            assert client.get("/api/v1/" + path).status_code == 401
        application.state.game = runtime
        application.dependency_overrides[get_game_service] = lambda: game
        application.dependency_overrides[get_current_user] = lambda: {
            "id": "test-owner",
            "username": "TestOwner",
        }
        result = client.get("/api/v1/company/analytics")
        assert result.status_code == 200
        assert result.json()["totals"]["completed_transports"] == 0
        assert (
            client.get("/api/v1/company/analytics?scope=model").status_code
            == 422
        )
        facility = client.get("/api/v1/map/facilities/berlin_westhafen").json()
        city_uid = facility["city_uid"]
        assert (
            client.get("/api/v1/map/cities/" + city_uid).json()["city_uid"]
            == city_uid
        )
        assert client.get("/api/v1/map/cities/Berlin").status_code == 404
        assert client.get("/api/v1/map/cities/unknown").status_code == 404
        assert client.get("/api/v1/map/facilities/unknown").status_code == 404
        assert (
            build_analytics_service(runtime, "test-owner").analyze(
                NOW, "30", "company", None
            )["status"]["vehicles"]
            == 1
        )
