"""Global reusable freight templates, independent of player state."""

import json

from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.snapshot_mapping import load_offer
from app.repositories.state_snapshots import decode_snapshot, encode_snapshot

TEMPLATE_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS market_templates ("
    "template_id TEXT PRIMARY KEY, city_uid TEXT NOT NULL, "
    "model_id TEXT NOT NULL, offer_snapshot TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS templates_scope "
    "ON market_templates(city_uid, model_id)",
)


class SqliteMarketTemplateStore:
    """Persist player-independent, reusable freight terms."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind the shared relational database."""
        self.database = database

    @staticmethod
    def initialize(database: SqliteGameDatabase) -> None:
        """Create global template storage during application startup."""
        with database.transaction(), database.connect() as connection:
            for statement in TEMPLATE_SCHEMA:
                connection.execute(statement)

    def templates(
        self, cities: tuple[str, ...]
    ) -> tuple[PreparedTemplate, ...]:
        """Read only templates within the demanded city identities."""
        with self.database.connect() as connection:
            rows = connection.execute(
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

    def scoped_templates(
        self, scopes: tuple[tuple[str, str], ...]
    ) -> tuple[PreparedTemplate, ...]:
        """Read exact city and model contexts with one set-based query."""
        if not scopes:
            return ()
        with self.database.connect() as connection:
            rows = connection.execute(
                "WITH requested AS (SELECT "
                "json_extract(value, '$[0]') AS city_uid, "
                "json_extract(value, '$[1]') AS model_id "
                "FROM json_each(?)) SELECT template.* "
                "FROM market_templates AS template JOIN requested "
                "USING(city_uid, model_id) ORDER BY template.rowid",
                (json.dumps(scopes),),
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

    def add(self, template: PreparedTemplate) -> None:
        """Insert immutable supply in the caller's transaction."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO market_templates VALUES (?, ?, ?, ?)",
                (
                    template.template_id,
                    template.city_uid,
                    template.model_id,
                    encode_snapshot("offer", template.offer),
                ),
            )
