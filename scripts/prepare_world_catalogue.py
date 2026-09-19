"""Explicitly back up and upgrade the supplied world reference catalogue."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_world_maintenance_service  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    configure_logging("INFO")
    entries = json.loads(args.evidence.read_text(encoding="utf-8"))
    backup_database(args.catalogue, args.backup)
    build_world_maintenance_service(args.catalogue).prepare(entries)
    print("World catalogue upgraded and verified; schema 3.0.0")
