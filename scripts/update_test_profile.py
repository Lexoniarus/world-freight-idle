"""Explicit local test-profile maintenance, separate from the HTTP API."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.bootstrap import build_profile_maintenance_service  # noqa: E402
from app.config import Settings  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def parse_assignments(values: list[str]) -> dict[str, str]:
    """Parse unique vehicle=model options without discarding duplicates."""
    assignments = {}
    for value in values:
        parts = value.split("=")
        if len(parts) != 2 or any(not part.strip() for part in parts):
            raise ValueError("Expected existing-vehicle-id=catalogue-model-id")
        vehicle_id, model_id = (part.strip() for part in parts)
        if vehicle_id in assignments:
            raise ValueError("Duplicate vehicle assignment: " + vehicle_id)
        assignments[vehicle_id] = model_id
    return assignments


def main() -> None:
    """Back up before applying an explicit local maintenance request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--vehicle",
        action="append",
        required=True,
        help="existing-vehicle-id=catalogue-model-id",
    )
    parser.add_argument("--cash", type=int, help="omit to preserve balance")
    args = parser.parse_args()
    try:
        assignments = parse_assignments(args.vehicle)
    except ValueError as exc:
        parser.error(str(exc))
    settings = Settings.from_env()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = settings.db_path.parent / "backups" / f"game-{timestamp}.db"
    backup_database(settings.db_path.resolve(), backup)
    service = build_profile_maintenance_service(settings)
    result = service.update_profile(args.username, assignments, args.cash)
    print(json.dumps({**result, "backup": str(backup)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
