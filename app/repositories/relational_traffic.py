"""Public traffic read model over relational dispatch records."""

from app.domain.read_ports import SharedTransport
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import load_transport_record


class SqliteTrafficReader:
    """Read live public traffic without exposing private trip economics."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        self._database = database

    def list_active_transports(
        self, active_at: float
    ) -> tuple[SharedTransport, ...]:
        """Filter owner/status/times in columns and retain route snapshots."""
        with self._database.connect() as connection:
            rows = connection.execute(
                """SELECT t.*, u.username, v.model_id, v.name AS model_name
                FROM transports t
                JOIN users u ON u.id=t.user_id
                JOIN owned_vehicles v ON v.user_id=t.user_id
                    AND v.vehicle_id=t.vehicle_id
                WHERE t.status='active' AND t.arrives_at > ?
                ORDER BY t.departed_at ASC, t.transport_id ASC""",
                (active_at,),
            ).fetchall()
        return tuple(project_traffic_row(dict(row)) for row in rows)


def project_traffic_row(row: dict) -> SharedTransport:
    """Validate the stored trip and expose only public tracking fields."""
    trip = load_transport_record(row)
    return SharedTransport(
        user_id=row["user_id"],
        username=row["username"],
        id=trip.id,
        vehicle_id=trip.vehicle_id,
        model_id=row["model_id"] or "",
        model_name=row["model_name"],
        departed_at=trip.departed_at,
        arrives_at=trip.arrives_at,
        coordinates=trip.route.coordinates,
    )
