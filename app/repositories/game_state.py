"""Player-scoped relational repository and SQLite unit of work."""

from contextlib import AbstractContextManager
from dataclasses import asdict, replace

from app.domain.contracts import ContractOffer
from app.domain.energy import EnergyProfile
from app.domain.errors import PersistenceError
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.state_ports import GameStateRepository
from app.domain.transports import ActiveTransport
from app.domain.validation import require_finite, require_identity
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.snapshot_mapping import load_location, load_offer
from app.repositories.state_snapshots import decode_snapshot, encode_snapshot
from app.repositories.transport_mapping import load_transport


class SqliteGameStateRepository:
    """Persist one player's entities without exposing SQL to use cases."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        require_identity(user_id, "Player identity")
        self._database = database
        self._user_id = user_id

    def get_player(self) -> PlayerState | None:
        """Read the stored authoritative counters, if initialized."""
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT cash, completed, reputation FROM player_states "
                "WHERE user_id = ?",
                (self._user_id,),
            ).fetchone()
        try:
            return PlayerState(*row) if row is not None else None
        except (ValueError, TypeError) as exc:
            raise PersistenceError(
                "Ungültige gespeicherte Spielerwerte."
            ) from exc

    def save_player(self, player: PlayerState) -> None:
        """Persist counters under this repository's owner identity."""
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO player_states VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    cash=excluded.cash, completed=excluded.completed,
                    reputation=excluded.reputation""",
                (
                    self._user_id,
                    player.cash,
                    player.completed,
                    player.reputation,
                ),
            )

    def list_vehicles(self) -> tuple[OwnedVehicle, ...]:
        """Read purchased values and historical locations for this owner."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM owned_vehicles WHERE user_id=? ORDER BY rowid",
                (self._user_id,),
            ).fetchall()
        return tuple(load_vehicle_record(dict(row)) for row in rows)

    def save_vehicle(self, vehicle: OwnedVehicle) -> None:
        """Save one vehicle without replacing other owned vehicles."""
        location = (
            encode_snapshot("location", asdict(vehicle.location))
            if vehicle.location is not None
            else None
        )
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO owned_vehicles VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, vehicle_id) DO UPDATE SET
                    name=excluded.name, mode=excluded.mode,
                    model_id=excluded.model_id,
                    capacity_tons=excluded.capacity_tons,
                    operating_cost_eur_per_km=
                        excluded.operating_cost_eur_per_km,
                    status=excluded.status,
                    facility_uid=excluded.facility_uid,
                    location_snapshot=excluded.location_snapshot,
                    energy_snapshot=excluded.energy_snapshot,
                    energy_level=excluded.energy_level,
                    top_speed_kmh=excluded.top_speed_kmh""",
                (
                    self._user_id,
                    vehicle.id,
                    vehicle.name,
                    vehicle.mode,
                    vehicle.model_id,
                    vehicle.capacity_tons,
                    vehicle.operating_cost_eur_per_km,
                    vehicle.status,
                    vehicle.facility_uid,
                    location,
                    encode_snapshot("energy", asdict(vehicle.energy)),
                    vehicle.energy_level,
                    vehicle.top_speed_kmh,
                ),
            )

    def list_offers(self) -> tuple[ContractOffer, ...]:
        """Read immutable offers without looking up current reference data."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM contract_offers WHERE user_id=? ORDER BY rowid",
                (self._user_id,),
            ).fetchall()
        return tuple(load_offer_record(dict(row)) for row in rows)

    def replace_offers(self, offers: tuple[ContractOffer, ...]) -> None:
        """Atomically replace the current market; duplicates roll back."""
        with self._database.transaction(), self._database.connect() as db:
            db.execute(
                "DELETE FROM contract_offers WHERE user_id=?",
                (self._user_id,),
            )
            db.executemany(
                "INSERT INTO contract_offers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        self._user_id,
                        offer.id,
                        offer.origin.facility_uid,
                        offer.destination.facility_uid,
                        offer.created_at,
                        offer.expires_at,
                        offer.market_model,
                        encode_snapshot("offer", asdict(offer)),
                    )
                    for offer in offers
                ],
            )

    def remove_offer(self, offer_id: str) -> None:
        """Consume only an offer belonging to this player."""
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM contract_offers WHERE user_id=? "
                "AND contract_id=?",
                (self._user_id, offer_id),
            )

    def list_transports(self) -> tuple[ActiveTransport, ...]:
        """Read complete history for explicit inventory reconciliation."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transports WHERE user_id=? ORDER BY rowid",
                (self._user_id,),
            ).fetchall()
        return tuple(load_transport_record(dict(row)) for row in rows)

    def list_active_transports(self) -> tuple[ActiveTransport, ...]:
        """Read pending deliveries without decoding settled history."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transports "
                "WHERE user_id=? AND status='active' ORDER BY rowid",
                (self._user_id,),
            ).fetchall()
        return tuple(load_transport_record(dict(row)) for row in rows)

    def list_due_transports(self, now: float) -> tuple[ActiveTransport, ...]:
        """Read this owner's active deliveries due at the supplied time."""
        require_finite(now, "Settlement time")
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM transports WHERE user_id=? "
                "AND status='active' AND arrives_at<=? ORDER BY rowid",
                (self._user_id, now),
            ).fetchall()
        return tuple(load_transport_record(dict(row)) for row in rows)

    def save_transport(self, transport: ActiveTransport) -> None:
        """Insert a dispatch or persist its sole allowed state transition."""
        with self._database.transaction(), self._database.connect() as db:
            prior = db.execute(
                "SELECT * FROM transports WHERE user_id=? AND transport_id=?",
                (self._user_id, transport.id),
            ).fetchone()
            if prior is not None:
                previous = load_transport_record(dict(prior))
                if (
                    previous.status != "active"
                    or transport.status != "settled"
                    or replace(
                        previous,
                        status=transport.status,
                        settled_at=transport.settled_at,
                    )
                    != transport
                ):
                    raise PersistenceError("Transporthistorie ist geschützt.")
            db.execute(
                """INSERT INTO transports VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, transport_id) DO UPDATE SET
                    status=excluded.status, settled_at=excluded.settled_at,
                    transport_snapshot=excluded.transport_snapshot""",
                (
                    self._user_id,
                    transport.id,
                    transport.vehicle_id,
                    transport.contract.id,
                    transport.origin.facility_uid,
                    transport.destination.facility_uid,
                    transport.status,
                    transport.departed_at,
                    transport.arrives_at,
                    transport.settled_at,
                    transport.operating_cost_eur,
                    transport.payout_eur,
                    encode_snapshot("transport", asdict(transport)),
                ),
            )

    def reset(self) -> None:
        """Remove one player's progress while retaining the account."""
        with self._database.transaction(), self._database.connect() as db:
            for table in (
                "transports",
                "contract_offers",
                "owned_vehicles",
                "player_states",
            ):
                db.execute(
                    f"DELETE FROM {table} WHERE user_id=?", (self._user_id,)
                )


class SqliteGameUnitOfWork:
    """Bind a player repository to the database transaction owner."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        self._database = database
        self.repository: GameStateRepository = SqliteGameStateRepository(
            database, user_id
        )

    def transaction(self) -> AbstractContextManager[None]:
        """Open or join a synchronous atomic use case."""
        return self._database.transaction()


def load_vehicle_record(row: dict) -> OwnedVehicle:
    """Hydrate relational vehicle columns and validate its saved location."""
    try:
        return OwnedVehicle(
            id=row["vehicle_id"],
            energy=EnergyProfile(
                **decode_snapshot("energy", row["energy_snapshot"])
            ),
            energy_level=row["energy_level"],
            top_speed_kmh=row["top_speed_kmh"],
            name=row["name"],
            mode=row["mode"],
            model_id=row["model_id"],
            capacity_tons=row["capacity_tons"],
            operating_cost_eur_per_km=row["operating_cost_eur_per_km"],
            status=row["status"],
            facility_uid=row["facility_uid"],
            location=(
                load_location(
                    decode_snapshot("location", row["location_snapshot"])
                )
                if row["location_snapshot"] is not None
                else None
            ),
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise PersistenceError("Fahrzeugdaten nicht lesbar.") from exc


def load_offer_record(row: dict) -> ContractOffer:
    """Require indexed columns to agree with historical contract facts."""
    try:
        offer = load_offer(decode_snapshot("offer", row["offer_snapshot"]))
        expected = (
            offer.id,
            offer.origin.facility_uid,
            offer.destination.facility_uid,
            offer.created_at,
            offer.expires_at,
            offer.market_model,
        )
        actual = tuple(
            row[key]
            for key in (
                "contract_id",
                "origin_facility_uid",
                "destination_facility_uid",
                "created_at",
                "expires_at",
                "market_model",
            )
        )
        if actual != expected:
            raise ValueError("Offer columns differ from snapshot")
        return offer
    except (ValueError, TypeError, KeyError) as exc:
        raise PersistenceError("Auftragsdaten nicht lesbar.") from exc


def load_transport_record(row: dict) -> ActiveTransport:
    """Validate lifecycle columns against the retained transport document."""
    try:
        trip = load_transport(
            decode_snapshot("transport", row["transport_snapshot"])
        )
        expected = (
            trip.id,
            trip.vehicle_id,
            trip.contract.id,
            trip.origin.facility_uid,
            trip.destination.facility_uid,
            trip.status,
            trip.departed_at,
            trip.arrives_at,
            trip.settled_at,
            trip.operating_cost_eur,
            trip.payout_eur,
        )
        actual = tuple(
            row[key]
            for key in (
                "transport_id",
                "vehicle_id",
                "contract_id",
                "origin_facility_uid",
                "destination_facility_uid",
                "status",
                "departed_at",
                "arrives_at",
                "settled_at",
                "operating_cost_eur",
                "payout_eur",
            )
        )
        if actual != expected:
            raise ValueError("Transport columns differ from snapshot")
        return trip
    except (ValueError, TypeError, KeyError) as exc:
        raise PersistenceError("Transportdaten nicht lesbar.") from exc
