from app.repositories.sqlite_store import SqliteStore


def test_store_connect_and_initialize(store: SqliteStore):
    with store.connect() as connection:
        names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert {"kv", "geocode_cache", "route_cache"}.issubset(names)


def test_store_json_roundtrip_and_delete(store: SqliteStore):
    assert store.get_json("missing", {"x": 1}) == {"x": 1}
    store.set_json("alpha", {"value": 3})
    assert store.get_json("alpha") == {"value": 3}
    store.delete_state_keys(("alpha",))
    assert store.get_json("alpha") is None


def test_store_geocode_cache_roundtrip(store: SqliteStore):
    assert store.get_geocode("a") is None
    store.put_geocode("a", 1.2, 3.4, "display")
    cached = store.get_geocode("a")
    assert cached is not None
    assert cached["lat"] == 1.2
    assert cached["display_name"] == "display"


def test_store_route_cache_roundtrip(store: SqliteStore):
    assert store.get_route("r") is None
    store.put_route("r", {"distance_km": 12})
    assert store.get_route("r") == {"distance_km": 12}
