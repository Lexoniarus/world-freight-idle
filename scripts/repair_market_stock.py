"""Inspect or explicitly repair duplicate prepared market stock."""

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_market_stock_maintenance  # noqa: E402
from app.config import Settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402


def main() -> None:
    """Run read-only inspection or one archived transactional cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    archive = args.archive
    if args.check and archive is not None:
        parser.error("Check mode does not create an archive.")
    if args.apply and archive is None:
        parser.error("Apply mode requires --archive outside the repository.")
    root = Path(__file__).resolve().parents[1]
    if archive is not None and root in archive.resolve().parents:
        parser.error("The private archive must stay outside the repository.")
    configure_logging("INFO")
    settings = Settings.from_env(root)
    service, database = build_market_stock_maintenance(settings)
    try:
        report: Mapping[str, int | str]
        if args.check:
            report = service.inspect()
        else:
            assert isinstance(archive, Path)
            report = service.apply(archive)
    finally:
        database.close()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
