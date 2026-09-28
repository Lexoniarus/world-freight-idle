"""Read-only routing diagnostics on the shared relational infrastructure."""

from app.repositories.game_database import SqliteGameDatabase


class SqliteRoutingAudit:
    """Aggregate persisted evidence without performing provider requests."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind an existing runtime database without creating game state."""
        self.database = database

    def report(self, facility_ids: tuple[str, ...] = ()) -> dict:
        """Report global outcomes and optionally focused facility attempts."""
        with self.database.connect() as conn:
            relations = [
                dict(row)
                for row in conn.execute(
                    "SELECT status, failure_category, COUNT(*) AS count "
                    "FROM routing_relations GROUP BY status, failure_category"
                )
            ]
            anchors = [
                dict(row)
                for row in conn.execute(
                    "SELECT method, validation_status, COUNT(*) AS count "
                    "FROM routing_anchors GROUP BY method, validation_status"
                )
            ]
            attempts = [
                dict(row)
                for row in conn.execute(
                    "SELECT method, outcome, COUNT(*) AS count "
                    "FROM routing_attempts GROUP BY method, outcome"
                )
            ]
            focused: list[dict] = []
            for uid in facility_ids:
                focused.extend(
                    dict(row)
                    for row in conn.execute(
                        "SELECT * FROM routing_attempts WHERE subject_id=? "
                        "ORDER BY attempt_id",
                        (uid,),
                    )
                )
        return {
            "relations": relations,
            "anchors": anchors,
            "attempts": attempts,
            "focused_attempts": focused,
        }
