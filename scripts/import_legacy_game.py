"""Inspect or import an offline KV game database into a new relational file."""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_game_importer  # noqa: E402
from app.config import Settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402


def main() -> None:
    """Back up before execution; never activate or overwrite a database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    configure_logging("INFO")
    now = time.time()
    settings = Settings.from_env()
    if args.check:
        if args.backup or args.output:
            parser.error("Check mode takes only --source.")
        report = build_game_importer(args.source, settings).inspect(now)
    else:
        if args.backup is None or args.output is None:
            parser.error("Execution requires --backup and --output.")
        paths = (args.source, args.backup, args.output)
        if len({path.resolve() for path in paths}) != 3:
            parser.error("Source, backup and output must be separate files.")
        if args.output.exists():
            parser.error("Output already exists; nothing will be overwritten.")
        backup_database(args.source, args.backup)
        report = build_game_importer(args.backup, settings).import_to(
            args.output, now
        )
    print(json.dumps(asdict(report), ensure_ascii=False))


if __name__ == "__main__":
    main()
