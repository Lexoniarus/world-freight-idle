"""Offline inventory and reconciled relational import."""

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.game_import import ExcludedOffer, GameImportReport
from app.domain.transports import ActiveTransport
from app.domain.validation import require_finite, require_identity
from app.domain.world_scopes import WorldScope
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameStateRepository
from app.repositories.legacy_import_mapping import LegacySnapshotReader

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImportedProfile:
    """Private inventory with credentials excluded from representations."""

    account: tuple[str, str, str, float] = field(repr=False)
    player: PlayerState
    vehicles: tuple[OwnedVehicle, ...]
    offers: tuple[ContractOffer, ...]
    transports: tuple[ActiveTransport, ...]
    excluded: tuple[ExcludedOffer, ...]


def read_legacy_json(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate document fields instead of silently dropping values."""
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("Duplicate legacy document fields.")
    return value


def validate_profile_links(profile: ImportedProfile) -> None:
    """Check ownership, unique identities and active vehicle reservations."""
    for collection in (profile.vehicles, profile.offers, profile.transports):
        if len({item.id for item in collection}) != len(collection):
            raise ValueError("Duplicate player-owned identities.")
    vehicles = {vehicle.id: vehicle for vehicle in profile.vehicles}
    reserved = set()
    for trip in profile.transports:
        if trip.vehicle_id not in vehicles:
            raise ValueError("Transport references an unknown vehicle.")
        if trip.status == "active":
            vehicle = vehicles[trip.vehicle_id]
            if trip.vehicle_id in reserved or vehicle.status != "enroute":
                raise ValueError("Conflicting active vehicle reservation.")
            if vehicle.facility_uid != trip.origin.facility_uid:
                raise ValueError("Travelling vehicle has changed location.")
            if vehicle.capacity_tons < trip.contract.tons:
                raise ValueError(
                    "Historical payload exceeds vehicle capacity."
                )
            reserved.add(trip.vehicle_id)
    if reserved != {v.id for v in profile.vehicles if v.status == "enroute"}:
        raise ValueError("Travelling vehicle has no active transport.")


class LegacyGameImporter:
    """Read only the offline source and write an exclusively created target."""

    def __init__(
        self,
        source: Path,
        world: WorldScope,
        market_model: str,
        exclude_global_demo: bool = False,
    ) -> None:
        self.source = source.resolve()
        self.reader = LegacySnapshotReader(world)
        self.market_model = market_model
        self.exclude_global_demo = exclude_global_demo

    def _read_profiles(self, now: float) -> tuple[ImportedProfile, ...]:
        """Inventory a consistent read transaction; reject unknown state."""
        require_finite(now, "Import time")
        try:
            with closing(
                sqlite3.connect(self.source.as_uri() + "?mode=ro", uri=True)
            ) as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if not {"kv", "users"} <= tables or tables - {
                    "kv",
                    "users",
                    "sessions",
                    "auth_attempts",
                    "geocode_cache",
                    "route_cache",
                }:
                    raise ValueError("Unknown legacy database schema.")
                if connection.execute("PRAGMA integrity_check").fetchall() != [
                    ("ok",)
                ]:
                    raise ValueError("Corrupt legacy database.")
                accounts = connection.execute(
                    "SELECT id,username,password_hash,created_at "
                    "FROM users ORDER BY id"
                ).fetchall()
                states = {}
                for key, encoded in connection.execute(
                    "SELECT key,value FROM kv"
                ):
                    value = json.loads(
                        encoded, object_pairs_hook=read_legacy_json
                    )
                    json.dumps(value, allow_nan=False)
                    states[key] = value
                profiles = tuple(
                    self._read_profile(account, states, now)
                    for account in accounts
                )
                if self.exclude_global_demo:
                    self._exclude_global_demo(states)
                if states:
                    raise ValueError(
                        "Unassigned or unknown legacy state keys."
                    )
                return profiles
        except (
            sqlite3.Error,
            ValueError,
            KeyError,
            TypeError,
            StopIteration,
        ) as exc:
            LOGGER.error(
                "Legacy inventory rejected",
                extra={"event": "state.import_rejected"},
            )
            raise PersistenceError(
                "Legacy inventory invalid; source unchanged."
            ) from exc

    def _read_profile(
        self,
        account: tuple[str, str, str, float],
        states: dict[str, Any],
        now: float,
    ) -> ImportedProfile:
        """Map one owner; exclude only intact but unplayable offers."""
        user_id, username, password_hash, created_at = account
        for value in (user_id, username, password_hash):
            require_identity(value, "Account field")
        require_finite(created_at, "Account creation")
        prefix = f"user:{user_id}:"
        version = states.pop(prefix + "world_state_version", 1)
        if version != 1:
            raise ValueError("Unknown world-state revision.")
        player = PlayerState(**states.pop(prefix + "player"))
        vehicles = tuple(
            self.reader.vehicle(value)
            for value in states.pop(prefix + "vehicles")
        )
        offers = []
        excluded = []
        for value in states.pop(prefix + "contracts"):
            if "market_model" not in value:
                self.reader.validate_obsolete_offer(value)
                excluded.append(
                    ExcludedOffer(user_id, value["id"], "obsolete_goods_model")
                )
                continue
            offer = self.reader.offer(value)
            if offer.is_available(now, self.market_model):
                offers.append(offer)
            else:
                excluded.append(
                    ExcludedOffer(
                        user_id, offer.id, "expired_or_incompatible_market"
                    )
                )
        raw_trips = states.pop(prefix + "active_trips")
        transports = tuple(self.reader.transport(value) for value in raw_trips)
        profile = ImportedProfile(
            account,
            player,
            vehicles,
            tuple(offers),
            transports,
            tuple(excluded),
        )
        validate_profile_links(profile)
        return profile

    def _exclude_global_demo(self, states: dict[str, Any]) -> None:
        """Leave the explicitly approved unassigned demo only in its backup."""
        required = {"player", "vehicles", "contracts", "active_trips"}
        if not required <= states.keys() or states["active_trips"]:
            raise ValueError("Global demo is missing or contains transports.")
        if states.get("world_state_version", 1) != 1:
            raise ValueError("Unknown global world-state revision.")
        PlayerState(**states["player"])
        for vehicle in states["vehicles"]:
            self.reader.vehicle(vehicle)
        for offer in states["contracts"]:
            self.reader.validate_obsolete_offer(offer)
        for key in required | {"world_state_version"}:
            states.pop(key, None)
        LOGGER.info(
            "Authorized global demo retained in backup",
            extra={"event": "state.import_demo_excluded"},
        )

    def inspect(self, now: float) -> GameImportReport:
        """Validate and count a source without opening any destination."""
        return summarize_import(self._read_profiles(now))

    def import_to(self, target: Path, now: float) -> GameImportReport:
        """Create, atomically populate and reconcile a separate database."""
        profiles = self._read_profiles(now)
        target = target.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb"):
            pass
        try:
            database = SqliteGameDatabase(target)
            database.initialize()
            with database.transaction():
                self._write_profiles(database, profiles)
                reconcile_import(database, profiles)
            report = summarize_import(profiles)
            LOGGER.info(
                "Legacy import reconciled",
                extra={
                    "event": "state.import_completed",
                    "data": {
                        "accounts": report.accounts,
                        "vehicles": report.vehicles,
                        "offers": report.offers,
                        "transports": report.transports,
                        "excluded_offers": len(report.excluded_offers),
                    },
                },
            )
            return report
        except BaseException:
            target.unlink(missing_ok=True)
            LOGGER.error(
                "Legacy import rolled back",
                extra={"event": "state.import_rolled_back"},
            )
            raise

    def _write_profiles(
        self,
        database: SqliteGameDatabase,
        profiles: tuple[ImportedProfile, ...],
    ) -> None:
        """Write accounts and typed state inside the import transaction."""
        with database.connect() as connection:
            connection.executemany(
                "INSERT INTO users VALUES (?, ?, ?, ?)",
                [p.account for p in profiles],
            )
        for profile in profiles:
            repository = SqliteGameStateRepository(
                database, profile.account[0]
            )
            repository.save_player(profile.player)
            for vehicle in profile.vehicles:
                repository.save_vehicle(vehicle)
            repository.replace_offers(profile.offers)
            for trip in profile.transports:
                repository.save_transport(trip)


def summarize_import(
    profiles: tuple[ImportedProfile, ...],
) -> GameImportReport:
    """Count the complete inventory without exposing private account data."""
    return GameImportReport(
        len(profiles),
        sum(len(p.vehicles) for p in profiles),
        sum(len(p.offers) for p in profiles),
        sum(len(p.transports) for p in profiles),
        tuple(item for p in profiles for item in p.excluded),
    )


def reconcile_import(
    database: SqliteGameDatabase, profiles: tuple[ImportedProfile, ...]
) -> None:
    """Compare retained values and SQL integrity before commit."""
    with database.connect() as connection:
        accounts = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT id,username,password_hash,created_at "
                "FROM users ORDER BY id"
            )
        )
        if accounts != tuple(p.account for p in profiles):
            raise PersistenceError("Account reconciliation failed.")
        if connection.execute("PRAGMA foreign_key_check").fetchall() or [
            row[0] for row in connection.execute("PRAGMA integrity_check")
        ] != ["ok"]:
            raise PersistenceError("Import integrity check failed.")
    for profile in profiles:
        repository = SqliteGameStateRepository(database, profile.account[0])
        if repository.get_player() != profile.player:
            raise PersistenceError("Player reconciliation failed.")
        for stored, expected in (
            (repository.list_vehicles(), profile.vehicles),
            (repository.list_offers(), profile.offers),
            (repository.list_transports(), profile.transports),
        ):
            if {item.id: item for item in stored} != {
                item.id: item for item in expected
            }:
                raise PersistenceError("Snapshot reconciliation failed.")
