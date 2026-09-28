"""Repair known incomplete historical approach metadata in an offline copy."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_transport_repair  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def main() -> None:
    """Require an independent backup, output and private original archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    configure_logging("INFO")
    if args.check:
        if args.backup or args.output or args.archive:
            parser.error("Check mode takes only --source.")
        report = build_transport_repair(args.source).inspect()
    else:
        if not all((args.backup, args.output, args.archive)):
            parser.error(
                "Execution requires --backup, --output and --archive."
            )
        paths = (args.source, args.backup, args.output, args.archive)
        if len({p.resolve() for p in paths}) != 4:
            parser.error("Source, backup, output and archive must differ.")
        if any(p.exists() for p in paths[1:]):
            parser.error("Outputs already exist; nothing will be overwritten.")
        backup_database(args.source, args.backup)
        report = build_transport_repair(args.backup).repair_to(
            args.output,
            args.archive,
        )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
