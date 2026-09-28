"""Upgrade non-expiring market stock offline after a mandatory backup."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_market_stock_upgrade  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def main() -> None:
    """Inspect read-only or create a backed-up separate verified database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configure_logging("INFO")
    now = time.time()
    if args.check:
        if args.backup or args.output:
            parser.error("Check mode takes only --source.")
        report = build_market_stock_upgrade(args.source, now).inspect()
    else:
        if args.backup is None or args.output is None:
            parser.error("Execution requires --backup and --output.")
        paths = (args.source, args.backup, args.output)
        if len({p.resolve() for p in paths}) != 3 or any(
            p.exists() for p in paths[1:]
        ):
            parser.error("Choose distinct new output and backup paths.")
        backup_database(args.source, args.backup)
        report = build_market_stock_upgrade(args.backup, now).upgrade_to(
            args.output
        )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
