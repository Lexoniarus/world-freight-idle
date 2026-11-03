"""Private offer bindings to immutable routing revisions."""

from app.domain.routing_readiness import RouteReference
from app.repositories.game_database import SqliteGameDatabase


class SqliteOfferRouteStore:
    """Project open-offer references without changing snapshots."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        """Bind infrastructure references to one authenticated owner."""
        self.database = database
        self.user_id = user_id

    def get(self, offer_id: str) -> RouteReference | None:
        """Read only the bound player's open-offer reference."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT relation_id, revision FROM offer_route_references "
                "WHERE user_id=? AND contract_id=?",
                (self.user_id, offer_id),
            ).fetchone()
        return RouteReference(*row) if row is not None else None

    def get_many(
        self, offer_ids: tuple[str, ...]
    ) -> dict[str, RouteReference]:
        """Read the requested player bindings with one bounded query."""
        unique_ids = tuple(dict.fromkeys(offer_ids))
        if not unique_ids:
            return {}
        placeholders = ",".join("?" for _ in unique_ids)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT contract_id, relation_id, revision "
                "FROM offer_route_references WHERE user_id=? "
                f"AND contract_id IN ({placeholders})",
                (self.user_id, *unique_ids),
            ).fetchall()
        return {row[0]: RouteReference(row[1], row[2]) for row in rows}

    def replace(
        self, references: tuple[tuple[str, RouteReference], ...]
    ) -> None:
        """Replace bindings atomically, joining the market transaction."""
        with (
            self.database.transaction(),
            self.database.connect() as connection,
        ):
            current = tuple(
                (row[0], RouteReference(row[1], row[2]))
                for row in connection.execute(
                    "SELECT contract_id, relation_id, revision "
                    "FROM offer_route_references WHERE user_id=? "
                    "ORDER BY contract_id",
                    (self.user_id,),
                )
            )
            expected = tuple(sorted(references, key=lambda item: item[0]))
            if current == expected:
                return
            connection.execute(
                "DELETE FROM offer_route_references WHERE user_id=?",
                (self.user_id,),
            )
            connection.executemany(
                "INSERT INTO offer_route_references VALUES (?, ?, ?, ?)",
                (
                    (self.user_id, offer_id, ref.relation_id, ref.revision)
                    for offer_id, ref in references
                ),
            )
