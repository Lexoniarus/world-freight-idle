"""Canonical bounded and cached public traffic reads over SQLite."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Literal

from app.domain.errors import PersistenceError
from app.domain.read_ports import (
    MAX_PUBLIC_TRAFFIC_TRANSPORTS,
    MovementSegment,
    SharedTransport,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import load_transport_record
from app.repositories.transport_mapping import (
    load_journey,
    validate_transport_envelope,
)

TRAFFIC_FROM_SQL = """
    FROM transports t
    JOIN users u ON u.id=t.user_id
    JOIN owned_vehicles v ON v.user_id=t.user_id
        AND v.vehicle_id=t.vehicle_id
    LEFT JOIN account_preferences p ON p.user_id=t.user_id
    WHERE t.status='active' AND t.arrives_at > ?
    ORDER BY t.departed_at DESC, t.user_id ASC, t.vehicle_id ASC
    LIMIT ?
"""


@dataclass(frozen=True, slots=True)
class TrafficCacheEntry:
    """Retain one viewer-independent public snapshot for a bounded time."""

    expires_at: float
    selected_at: float
    active_until: float
    rows: tuple[SharedTransport, ...]


class SqliteTrafficReader:
    """Own public traffic selection, projection and shared snapshot caching."""

    def __init__(
        self,
        database: SqliteGameDatabase,
        maximum_transports: int = MAX_PUBLIC_TRAFFIC_TRANSPORTS,
        cache_seconds: float = 10,
        cache_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Bind an explicitly initialized public-read schema."""
        if maximum_transports <= 0:
            raise ValueError("Traffic limit must be positive.")
        if cache_seconds <= 0:
            raise ValueError("Traffic cache duration must be positive.")
        self._database = database
        self._maximum_transports = maximum_transports
        self._cache_seconds = cache_seconds
        self._cache_clock = cache_clock
        self._cache: dict[str, TrafficCacheEntry] = {}
        self._cache_lock = Lock()

    @staticmethod
    def initialize(database: SqliteGameDatabase) -> None:
        """Create the global active-traffic selection index explicitly."""
        with database.connect() as connection:
            connection.execute(
                "CREATE INDEX IF NOT EXISTS public_active_traffic "
                "ON transports(departed_at DESC, user_id, vehicle_id, "
                "arrives_at) WHERE status='active'"
            )

    def list_active_transports(
        self, active_at: float
    ) -> tuple[SharedTransport, ...]:
        """Return bounded public transports including immutable geometry."""
        return self._read("full", active_at)

    def list_active_summaries(
        self, active_at: float
    ) -> tuple[SharedTransport, ...]:
        """Return bounded public movement scalars without road geometry."""
        return self._read("summary", active_at)

    def _read(
        self,
        representation: Literal["full", "summary"],
        active_at: float,
    ) -> tuple[SharedTransport, ...]:
        """Reuse one shared snapshot until time or arrival invalidates it."""
        with self._cache_lock:
            now = self._cache_clock()
            cached = self._cache.get(representation)
            if (
                cached is not None
                and now < cached.expires_at
                and active_at >= cached.selected_at
                and active_at < cached.active_until
            ):
                return cached.rows
            rows = self._query(representation, active_at)
            active_until = min(
                (row.arrives_at for row in rows),
                default=float("inf"),
            )
            self._cache[representation] = TrafficCacheEntry(
                now + self._cache_seconds,
                active_at,
                active_until,
                rows,
            )
            return rows

    def _query(
        self,
        representation: Literal["full", "summary"],
        active_at: float,
    ) -> tuple[SharedTransport, ...]:
        """Execute the canonical indexed selection for one representation."""
        if representation == "full":
            columns = (
                "t.*, u.username, v.model_id, v.name AS model_name, "
                "p.company_color"
            )
            project = project_traffic_row
        else:
            columns = (
                "t.user_id, t.transport_id, t.vehicle_id, t.departed_at, "
                "t.arrives_at, u.username, v.model_id, "
                "v.name AS model_name, p.company_color, "
                "json_extract(t.transport_snapshot, '$.version') AS version, "
                "json_extract(t.transport_snapshot, '$.kind') AS kind, "
                "json_extract(t.transport_snapshot, '$.data.journey') "
                "AS journey"
            )
            project = project_traffic_summary_row
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT " + columns + TRAFFIC_FROM_SQL,
                (active_at, self._maximum_transports),
            ).fetchall()
        return tuple(project(dict(row)) for row in rows)


def project_traffic_row(row: dict) -> SharedTransport:
    """Validate a stored trip and expose only public tracking fields."""
    trip = load_transport_record(row)
    return SharedTransport(
        user_id=row["user_id"],
        company_color=row.get("company_color"),
        username=row["username"],
        id=trip.id,
        vehicle_id=trip.vehicle_id,
        model_id=row["model_id"] or "",
        model_name=row["model_name"],
        departed_at=trip.departed_at,
        arrives_at=trip.arrives_at,
        coordinates=trip.route.coordinates,
        route_legs=trip.dispatch_route.legs if trip.dispatch_route else (),
        distance_km=trip.journey.distance_km,
        segments=tuple(
            MovementSegment(
                part.phase,
                part.starts_at,
                part.ends_at,
                part.start_km,
                part.end_km,
            )
            for part in trip.journey.segments
        ),
    )


def project_traffic_summary_row(row: dict) -> SharedTransport:
    """Project typed public intervals without returning private energy."""
    try:
        validate_transport_envelope(row)
        journey = load_journey(json.loads(row["journey"]))
        return SharedTransport(
            user_id=row["user_id"],
            username=row["username"],
            id=row["transport_id"],
            vehicle_id=row["vehicle_id"],
            model_id=row["model_id"] or "",
            model_name=row["model_name"],
            departed_at=row["departed_at"],
            arrives_at=row["arrives_at"],
            coordinates=(),
            distance_km=journey.distance_km,
            segments=tuple(
                MovementSegment(
                    part.phase,
                    part.starts_at,
                    part.ends_at,
                    part.start_km,
                    part.end_km,
                )
                for part in journey.segments
            ),
            company_color=row["company_color"],
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise PersistenceError("Verkehrsdaten nicht lesbar.") from exc
