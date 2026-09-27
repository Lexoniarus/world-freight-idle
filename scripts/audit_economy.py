"""Write a reproducible catalogue economy matrix without player access."""

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_economy_audit
from app.domain.economy_audit import EconomyMatrixRow
from app.services.economy_audit import summarize_economy


def project_row(row: EconomyMatrixRow) -> dict[str, Any]:
    """Flatten a typed scenario into the unchanged CSV columns."""
    values = asdict(row)
    result = values.pop("result")
    if result is None:
        for key in ("load_case", "approach_km", "starting_fraction"):
            values.pop(key)
    else:
        values.update(result)
    return values


def main() -> None:
    """Write local CSV and summary artifacts for review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/economy")
    )
    options = parser.parse_args()
    matrix = build_economy_audit(
        Path(__file__).resolve().parents[1], 20260925
    ).matrix()
    rows = [project_row(row) for row in matrix]
    options.output.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (options.output / "matrix.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {"seed": 20260925, **asdict(summarize_economy(matrix))}
    (options.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    if summary["reference_min_margin"] < 0.20:
        raise SystemExit("Reference margin below agreed target")


if __name__ == "__main__":
    main()
