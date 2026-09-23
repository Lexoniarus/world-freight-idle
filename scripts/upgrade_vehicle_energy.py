"""Explicit offline schema 1.0.0 to 1.1.0 upgrade with mandatory backup."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_energy_upgrade  # noqa: E402
from app.config import Settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def main() -> None:
    """Validate arguments, back up before execution and report only counts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configure_logging("INFO")
    settings = Settings.from_env()
    if args.check:
        if args.backup or args.output:
            parser.error("Check mode takes only --source.")
        report = build_energy_upgrade(args.source, settings).inspect()
    else:
        if args.backup is None or args.output is None:
            parser.error("Execution requires --backup and --output.")
        if (
            len({p.resolve() for p in (args.source, args.backup, args.output)})
            != 3
        ):
            parser.error("Source, backup and output must be separate files.")
        if args.output.exists():
            parser.error("Output already exists; nothing will be overwritten.")
        backup_database(args.source, args.backup)
        report = build_energy_upgrade(args.backup, settings).upgrade_to(
            args.output
        )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
