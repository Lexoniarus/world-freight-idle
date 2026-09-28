"""Relational reusable templates and atomic private issuance/consumption."""

import json

from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.market_stock import MarketArrival, PreparedTemplate, TradeKey
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.snapshot_mapping import load_location, load_offer
from app.repositories.state_snapshots import decode_snapshot, encode_snapshot

STOCK_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS market_templates ("
    "template_id TEXT PRIMARY KEY, city_uid TEXT NOT NULL, "
    "model_id TEXT NOT NULL, offer_snapshot TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS templates_scope "
    "ON market_templates(city_uid, model_id)",
    "CREATE TABLE IF NOT EXISTS market_offer_templates ("
    "user_id TEXT NOT NULL, contract_id TEXT NOT NULL, "
    "template_id TEXT NOT NULL REFERENCES market_templates(template_id), "
    "PRIMARY KEY(user_id, template_id), UNIQUE(user_id, contract_id), "
    "FOREIGN KEY(user_id, contract_id) REFERENCES "
    "contract_offers(user_id, contract_id) ON DELETE CASCADE)",
    "CREATE TABLE IF NOT EXISTS market_template_uses ("
    "user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "template_id TEXT NOT NULL REFERENCES market_templates(template_id), "
    "used_at REAL NOT NULL, PRIMARY KEY(user_id, template_id))",
    "CREATE TABLE IF NOT EXISTS market_stock_cursors ("
    "user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, "
    "context TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS market_stock_pending ("
    "user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, "
    "context TEXT NOT NULL, origin_uid TEXT NOT NULL, "
    "destination_uid TEXT NOT NULL, cargo_id INTEGER NOT NULL, "
    "PRIMARY KEY(user_id, context))",
)


class SqliteMarketStockStore:
    """Bind private use records while sharing the same global template pool."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        """Inject existing storage; schema creation belongs to startup."""
        self.database = database
        self.user_id = user_id

    @staticmethod
    def initialize(database: SqliteGameDatabase) -> None:
        """Create additive stock infrastructure before serving requests."""
        with database.transaction(), database.connect() as db:
            for statement in STOCK_SCHEMA:
                db.execute(statement)

    def templates(
        self, cities: tuple[str, ...]
    ) -> tuple[PreparedTemplate, ...]:
        """Read only templates within the demanded city identities."""
        with self.database.connect() as db:
            rows = db.execute(
                "SELECT * FROM market_templates WHERE city_uid IN "
                "(SELECT value FROM json_each(?)) ORDER BY rowid",
                (json.dumps(cities),),
            ).fetchall()
        try:
            return tuple(
                PreparedTemplate(
                    row["template_id"],
                    row["model_id"],
                    row["city_uid"],
                    load_offer(
                        decode_snapshot("offer", row["offer_snapshot"])
                    ),
                )
                for row in rows
            )
        except (ValueError, TypeError, KeyError) as exc:
            raise PersistenceError("Auftragsvorlage nicht lesbar.") from exc

    def used(self) -> frozenset[str]:
        """Read this account's permanent consumption ledger."""
        with self.database.connect() as db:
            return frozenset(
                row[0]
                for row in db.execute(
                    "SELECT template_id FROM market_template_uses "
                    "WHERE user_id=?",
                    (self.user_id,),
                )
            )

    def bindings(self) -> dict[str, str]:
        """Index already issued offers without loading their snapshots."""
        with self.database.connect() as db:
            return dict(
                db.execute(
                    "SELECT template_id, contract_id "
                    "FROM market_offer_templates "
                    "WHERE user_id=?",
                    (self.user_id,),
                )
            )

    def add(self, template: PreparedTemplate) -> None:
        """Insert immutable supply in the caller's publication transaction."""
        with self.database.connect() as db:
            db.execute(
                "INSERT INTO market_templates VALUES (?, ?, ?, ?)",
                (
                    template.template_id,
                    template.city_uid,
                    template.model_id,
                    encode_snapshot("offer", template.offer),
                ),
            )

    def issue(self, template_id: str, offer: ContractOffer) -> None:
        """Atomically issue a private snapshot only for an unused template."""
        with self.database.transaction(), self.database.connect() as db:
            if db.execute(
                "SELECT 1 FROM market_template_uses "
                "WHERE user_id=? AND template_id=?",
                (self.user_id, template_id),
            ).fetchone():
                raise ValueError("Auftragsvorlage bereits verwendet.")
            db.execute(
                "INSERT INTO contract_offers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.user_id,
                    offer.id,
                    offer.origin.facility_uid,
                    offer.destination.facility_uid,
                    offer.created_at,
                    offer.expires_at,
                    offer.market_model,
                    encode_snapshot("offer", offer),
                ),
            )
            db.execute(
                "INSERT INTO market_offer_templates VALUES (?, ?, ?)",
                (self.user_id, offer.id, template_id),
            )

    def consume(self, offer_id: str, now: float) -> None:
        """Record once-per-account use inside the dispatch transaction."""
        with self.database.transaction(), self.database.connect() as db:
            row = db.execute(
                "SELECT template_id FROM market_offer_templates "
                "WHERE user_id=? AND contract_id=?",
                (self.user_id, offer_id),
            ).fetchone()
            if row is not None:
                if db.execute(
                    "SELECT 1 FROM market_template_uses "
                    "WHERE user_id=? AND template_id=?",
                    (self.user_id, row[0]),
                ).fetchone():
                    raise ValueError("Auftragsvorlage bereits verwendet.")
                db.execute(
                    "INSERT INTO market_template_uses VALUES (?, ?, ?)",
                    (self.user_id, row[0], now),
                )

    def arrivals(self, until: float) -> tuple[MarketArrival, ...]:
        """Project pending destination facts without deserializing roads."""
        with self.database.connect() as db:
            rows = db.execute(
                "SELECT transport_id, vehicle_id, arrives_at, "
                "destination_facility_uid, json_extract(transport_snapshot, "
                "'$.data.destination') AS destination FROM transports "
                "WHERE user_id=? AND status='active' AND arrives_at<=? "
                "ORDER BY arrives_at, transport_id",
                (self.user_id, until),
            ).fetchall()
        result = []
        try:
            for row in rows:
                location = load_location(json.loads(row["destination"]))
                if location.facility_uid != row["destination_facility_uid"]:
                    raise ValueError("Arrival location differs.")
                result.append(
                    MarketArrival(
                        row["transport_id"],
                        row["vehicle_id"],
                        location,
                        row["arrives_at"],
                    )
                )
        except (ValueError, TypeError, KeyError) as exc:
            raise PersistenceError("Ankunft nicht lesbar.") from exc
        return tuple(result)

    def cursor(self) -> str:
        """Resume fair context rotation after a worker restart."""
        with self.database.connect() as db:
            row = db.execute(
                "SELECT context FROM market_stock_cursors WHERE user_id=?",
                (self.user_id,),
            ).fetchone()
        return row[0] if row else ""

    def pending(self, context: str) -> TradeKey | None:
        """Resume one partially checked candidate instead of rerolling it."""
        with self.database.connect() as db:
            row = db.execute(
                "SELECT origin_uid, destination_uid, cargo_id "
                "FROM market_stock_pending WHERE user_id=? AND context=?",
                (self.user_id, context),
            ).fetchone()
        return (row[0], row[1], row[2]) if row else None

    def checkpoint(self, context: str, trade: TradeKey | None) -> None:
        """Persist fair rotation and the selected partial route atomically."""
        with self.database.transaction(), self.database.connect() as db:
            db.execute(
                "INSERT INTO market_stock_cursors VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET context=excluded.context",
                (self.user_id, context),
            )
            db.execute(
                "DELETE FROM market_stock_pending WHERE user_id=? "
                "AND context=?",
                (self.user_id, context),
            )
            if trade is not None:
                db.execute(
                    "INSERT INTO market_stock_pending VALUES (?, ?, ?, ?, ?)",
                    (self.user_id, context, *trade),
                )
