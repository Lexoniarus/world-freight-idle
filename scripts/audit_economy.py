"""Write a reproducible catalogue economy matrix without player access."""

import argparse
import csv
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.economics import VehicleCostProfile
from app.domain.economy_audit import audit_economy_case
from app.domain.market import MarketVehicle
from app.domain.market_compatibility import vehicle_suitability
from app.domain.market_profiles import vehicle_scale_for_segment
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue


def matrix(root: Path) -> list[dict[str, Any]]:
    """Enumerate compatibility and low, generated median, high scenarios."""
    models = SqliteVehicleCatalogue(
        root / "data/world_freight_vehicle_catalog.sqlite3"
    ).list_models()
    world = SqliteWorldCatalogue(
        root / "data/world_freight_company_facility_mvp.sqlite3"
    ).read()
    reference = min(p.freight_rate_factor_game for p in world.market_profiles)
    rng = random.Random(20260925)
    distances = {"short": 75, "medium": 375, "long": 1000}
    rows = []
    for model in models:
        vehicle = MarketVehicle(
            "audit",
            model.id,
            "audit-city",
            "truck",
            model.capacity_tons,
            vehicle_scale_for_segment(model.segment),
            model.transport_capabilities,
            VehicleCostProfile(model.maintenance_eur_per_1000_km / 1000),
            model.energy,
        )
        for profile in world.market_profiles:
            for load in profile.distance_profiles:
                identity = {
                    "model_id": model.id,
                    "scale": vehicle.scale,
                    "nhm_row_id": profile.nhm_row_id,
                    "band": load.distance_band,
                    "load_min": load.load_factor_min,
                    "load_max": load.load_factor_max,
                }
                if (
                    vehicle_suitability(vehicle, profile) <= 0
                    or load.selection_weight <= 0
                ):
                    rows.append({**identity, "compatible": False})
                    continue
                typical = sorted(rng.random() for _ in range(101))[50]
                for label, draw in (
                    ("low", 0),
                    ("typical", typical),
                    ("high", 1),
                ):
                    for approach, starting in ((0, 1), (10, 0.5), (50, 0.1)):
                        result = audit_economy_case(
                            vehicle,
                            profile,
                            load,
                            reference,
                            draw,
                            distances[load.distance_band],
                            approach,
                            starting,
                        )
                        rows.append(
                            {
                                **identity,
                                "compatible": True,
                                "load_case": label,
                                "approach_km": approach,
                                "starting_fraction": starting,
                                **asdict(result),
                            }
                        )
    return rows


def main() -> None:
    """Write local CSV and summary artifacts for review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/economy")
    )
    options = parser.parse_args()
    rows = matrix(Path(__file__).resolve().parents[1])
    options.output.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (options.output / "matrix.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    compatible = [row for row in rows if row["compatible"]]
    summary = {
        "seed": 20260925,
        "models": len({row["model_id"] for row in rows}),
        "rows": len(rows),
        "incompatible_rows": len(rows) - len(compatible),
        "reference_min_margin": min(
            row["reference_margin"] for row in compatible
        ),
        "negative_cashflow_rows": sum(
            row["booked_profit_eur"] < 0 for row in compatible
        ),
        "typical_negative_cashflow_rows": sum(
            row["booked_profit_eur"] < 0 and row["load_case"] == "typical"
            for row in compatible
        ),
    }
    (options.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    if summary["reference_min_margin"] < 0.20:
        raise SystemExit("Reference margin below agreed target")


if __name__ == "__main__":
    main()
