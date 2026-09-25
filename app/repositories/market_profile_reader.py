"""Read the complete immutable Market v2 reference profiles."""

import sqlite3

from app.domain.market_profiles import (
    DistanceLoadProfile,
    NhmMarketProfile,
    VehicleScaleProfile,
    require_unit_weight,
)


def read_market_profiles(
    connection: sqlite3.Connection,
) -> tuple[NhmMarketProfile, ...]:
    """Validate all profile rows and require every operative NHM node."""
    distances: dict[int, list[DistanceLoadProfile]] = {}
    for row in connection.execute("SELECT * FROM nhm_distance_load_profiles"):
        distances.setdefault(row["nhm_row_id"], []).append(
            DistanceLoadProfile(
                row["distance_band"],
                row["selection_weight"],
                row["load_factor_min"],
                row["load_factor_max"],
            )
        )
    scales: dict[int, list[VehicleScaleProfile]] = {}
    for row in connection.execute("SELECT * FROM nhm_vehicle_scale_profiles"):
        scales.setdefault(row["nhm_row_id"], []).append(
            VehicleScaleProfile(row["vehicle_scale"], row["suitability_game"])
        )
    profiles = []
    for row in connection.execute("SELECT * FROM nhm_market_profiles"):
        require_unit_weight(row["value_confidence"])
        profiles.append(
            NhmMarketProfile(
                row["nhm_row_id"],
                row["transport_class"],
                row["value_eur_per_t"],
                row["freight_rate_factor_game"],
                tuple(distances.get(row["nhm_row_id"], [])),
                tuple(scales.get(row["nhm_row_id"], [])),
            )
        )
    operational = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT nhm_row_id FROM facility_nhm_profiles"
        )
    }
    if not operational <= {p.nhm_row_id for p in profiles}:
        raise ValueError("Operative NHM node without market profile.")
    return tuple(profiles)
