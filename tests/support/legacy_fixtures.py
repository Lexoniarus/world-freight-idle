"""Reusable fixtures for the legacy game import boundary."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace

import pytest

from app.api.v1.game_projection import (
    project_contract,
    project_transport,
    project_vehicle,
)
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.world_scopes import WorldScope
from app.repositories.legacy_game_import import LegacyGameImporter
from app.services.auth import PasswordHasher


def legacy_vehicle_projection(vehicle):
    """Build only pre-energy fields for the old-format fixture."""
    return {
        key: value
        for key, value in project_vehicle(vehicle).items()
        if key not in {"energy", "energy_level", "top_speed_kmh"}
    }


def legacy_transport_projection(trip):
    """Build the pre-energy transport contract."""
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
            "cost_breakdown",
        }
    }


@pytest.fixture
def legacy_source(tmp_path, synthetic_game):
    """Build a representative pre-relational game database."""
    now = synthetic_game.now()
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    offer = next(
        item
        for item in synthetic_game.state_repository.list_offers()
        if item.origin.facility_uid == vehicle.facility_uid
        and item.tons <= vehicle.capacity_tons
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
            ((13.0, 52.0), (14.0, 53.0)),
            100,
            120,
            "saved-provider",
        ),
        now - 120,
        now - 1,
        987,
        142,
        journey=unmetered_journey(100, (now - 1) - (now - 120)),
    )
    vehicle.start_trip()
    expired = replace(
        offer,
        id="expired",
        created_at=now - 2000,
        expires_at=now - 1000,
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
        connection.executescript(
            """
CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,password_hash TEXT,created_at REAL);
CREATE TABLE kv(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE sessions(token_hash TEXT,user_id TEXT,expires_at REAL);
CREATE TABLE route_cache(cache_key TEXT,payload TEXT,updated_at REAL);
"""
        )
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
        WorldScope(synthetic_game.world.read()),
        "nhm_v1",
        synthetic_game.catalogue.list_models(),
    )
    return path, importer, state, now, password_hash


def update_legacy(path, key, value) -> None:
    """Replace one legacy key-value document."""
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE kv SET value=? WHERE key=?",
            (json.dumps(value), key),
        )
        connection.commit()
