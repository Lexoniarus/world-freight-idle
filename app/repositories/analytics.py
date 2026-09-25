"""SQLite JSON scalar projection; never hydrate historical transports."""

import math
from typing import Any

from app.domain.analytics import AnalyticsData
from app.domain.errors import PersistenceError
from app.repositories.game_database import SqliteGameDatabase

PROJECTION = """
SELECT transport_id, vehicle_id, status, arrives_at,
       payout_eur AS revenue_eur, operating_cost_eur,
       json_extract(transport_snapshot, '$.kind') AS kind,
       json_extract(transport_snapshot, '$.version') AS version,
       json_type(transport_snapshot, '$.version') AS version_type,
       json_extract(transport_snapshot, '$.data.contract.tons') AS tons,
       json_extract(transport_snapshot,
           '$.data.route.distance_km') AS distance_km,
       json_extract(transport_snapshot, '$.data.origin.city.city_uid') AS city,
       json_extract(transport_snapshot,
           '$.data.origin.city.name') AS city_name,
       json_extract(transport_snapshot,
           '$.data.contract.market_model') AS market_model,
       json_extract(transport_snapshot,
           '$.data.contract.market_context.transport_class')
           AS transport_class,
       json_extract(transport_snapshot,
           '$.data.contract.market_context.distance_band') AS distance_band,
       json_type(transport_snapshot, '$.data.contract.tons') AS tons_type,
       json_type(transport_snapshot,
           '$.data.route.distance_km') AS distance_type
FROM transports WHERE user_id = ? AND status = ? AND arrives_at <= ?
ORDER BY arrives_at, transport_id
"""


def validate_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate extracted fields without decoding the JSON document."""
    if (
        row["kind"] != "transport"
        or row["version"] != 2
        or row["version_type"] != "integer"
        or not isinstance(row["city"], str)
        or not row["city"]
        or not isinstance(row["city_name"], str)
        or row["tons_type"] not in {"integer", "real"}
        or row["distance_type"] not in {"integer", "real"}
        or any(
            not isinstance(row[key], (int, float))
            or not math.isfinite(row[key])
            or row[key] <= 0
            for key in ("tons", "distance_km")
        )
    ):
        raise PersistenceError("Historische Statistikdaten sind beschädigt.")
    if row["market_model"] != "nhm_v2":
        row["transport_class"] = None
        row["distance_band"] = None
    elif row["transport_class"] not in {
        "general",
        "parcel",
        "dry_bulk",
        "liquid_bulk",
        "temperature_controlled",
        "special",
    } or row["distance_band"] not in {"short", "medium", "long"}:
        raise PersistenceError("Historischer V2-Kontext ist beschädigt.")
    row["profit_eur"] = row["revenue_eur"] - row["operating_cost_eur"]
    row["vehicle"] = row["vehicle_id"]
    return row


class SqliteAnalyticsReader:
    """Own a session-bound, consistent read transaction."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        self.database = database
        self.user_id = user_id

    def read(self, now: float) -> AnalyticsData:
        """Select scalar values only; the all-time totals require history."""
        with self.database.connect() as db:
            db.execute("BEGIN")
            player = db.execute(
                "SELECT cash, completed, reputation FROM player_states "
                "WHERE user_id = ?",
                (self.user_id,),
            ).fetchone()
            if player is None:
                raise PersistenceError("Unternehmensstand fehlt.")
            status = dict(player)
            status.update(
                dict(
                    db.execute(
                        "SELECT COUNT(*) AS vehicles, "
                        "COALESCE(SUM(status='idle'),0) AS idle_vehicles, "
                        "COALESCE(SUM(status='enroute'),0) "
                        "AS enroute_vehicles, "
                        "COUNT(DISTINCT CASE WHEN status='idle' THEN "
                        "json_extract(location_snapshot, "
                        "'$.data.city.city_uid') "
                        "END) AS active_cities FROM owned_vehicles "
                        "WHERE user_id=?",
                        (self.user_id,),
                    ).fetchone()
                )
            )
            history = tuple(
                validate_row(dict(row))
                for row in db.execute(
                    PROJECTION,
                    (self.user_id, "settled", now),
                )
            )
            ongoing = tuple(
                dict(row)
                for row in db.execute(
                    "SELECT vehicle_id, payout_eur AS revenue_eur, "
                    "operating_cost_eur, payout_eur-operating_cost_eur "
                    "AS profit_eur FROM transports "
                    "WHERE user_id=? AND status='active'",
                    (self.user_id,),
                )
            )
            names = tuple(
                (row[0], row[1])
                for row in db.execute(
                    "SELECT vehicle_id, name FROM owned_vehicles "
                    "WHERE user_id=?",
                    (self.user_id,),
                )
            )
            db.commit()
        status["active_transports"] = len(ongoing)
        return AnalyticsData(status, history, ongoing, names)
