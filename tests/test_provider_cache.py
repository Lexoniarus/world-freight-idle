"""Provider cache replacement, corruption and storage failure contracts."""

import pytest

from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache


def test_provider_cache_replaces_invalid_documents(
    relational,
    caplog,
):
    caplog.set_level("WARNING", logger="app.repositories.provider_cache")
    cache = SqliteProviderCache(relational)
    assert cache.get_route("absent") is None
    assert cache.get_geocode("absent") is None
    cache.put_route("route", {"distance_km": 1})
    cache.put_route("route", {"distance_km": 2})
    assert cache.get_route("route") == {"distance_km": 2}
    with pytest.raises(PersistenceError):
        cache.put_route("route", {"distance_km": float("nan")})
    assert cache.get_route("route") == {"distance_km": 2}
    with relational.connect() as connection:
        connection.execute("UPDATE route_cache SET payload='not json'")
    assert cache.get_route("route") is None
    assert any(
        getattr(record, "event", None) == "cache.invalid_route"
        for record in caplog.records
    )
    cache.put_route("route", {"distance_km": 3})
    assert cache.get_route("route") == {"distance_km": 3}
    cache.put_geocode("address", 52, 13, "First")
    cache.put_geocode("address", 53, 14, "Second")
    found = cache.get_geocode("address")
    assert found is not None
    assert found["display_name"] == "Second"
    assert (found["lat"], found["lon"]) == (53, 14)


def test_provider_cache_rejects_unavailable_storage(tmp_path):
    database = SqliteGameDatabase(tmp_path / "missing" / "game.db")

    with pytest.raises(PersistenceError):
        SqliteProviderCache(database)
