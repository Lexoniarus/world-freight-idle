"""Inspect or repair historical repetitive market stock in a new copy."""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_market_stock_repair  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def main() -> None:
    """Require independent artifacts and never update the source in place."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--archive", type=Path)
    arguments = parser.parse_args()
    configure_logging("INFO")
    if arguments.check:
        if arguments.backup or arguments.output or arguments.archive:
            parser.error("Check mode takes only --source.")
        report = build_market_stock_repair(arguments.source).inspect()
    else:
        if not all((arguments.backup, arguments.output, arguments.archive)):
            parser.error(
                "Execution requires --backup, --output and --archive."
            )
        paths = (
            arguments.source,
            arguments.backup,
            arguments.output,
            arguments.archive,
        )
        if len({path.resolve() for path in paths}) != 4:
            parser.error("Source and maintenance artifacts must differ.")
        if any(path.exists() for path in paths[1:]):
            parser.error("Maintenance artifacts already exist.")
        backup_database(arguments.source, arguments.backup)
        report = build_market_stock_repair(arguments.backup).repair_to(
            arguments.output,
            arguments.archive,
            time.time(),
        )
    print(json.dumps(asdict(report), sort_keys=True))


if __name__ == "__main__":
    main()
