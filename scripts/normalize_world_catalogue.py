"""Back up and normalize reference geography using reviewed city identities."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_geography_migration  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402
from app.services.world_geography import (
    validate_geography_mapping,  # noqa: E402
)


def main() -> None:
    """Validate, back up, then write and reconcile a separate catalogue."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    args = parser.parse_args()
    if (
        len(
            {
                p.resolve()
                for p in (
                    args.catalogue,
                    args.backup,
                    args.output,
                )
            }
        )
        != 3
    ):
        parser.error("Source, backup and output must be separate files.")
    configure_logging("INFO")
    mapping = validate_geography_mapping(
        json.loads(args.mapping.read_text(encoding="utf-8"))
    )
    backup_database(args.catalogue, args.backup)
    build_geography_migration(args.backup, args.output).normalize(mapping)
    print("World catalogue normalized and reconciled; schema 4.0.0")


if __name__ == "__main__":
    main()
