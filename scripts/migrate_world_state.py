"""Back up and migrate stopped-server game state to durable facility IDs."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.bootstrap import build_world_state_migration_service  # noqa: E402
from app.config import Settings  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.repositories.database_backup import backup_database  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    configure_logging("INFO")
    settings = Settings.from_env()
    backup_database(settings.db_path, args.backup)
    changed = build_world_state_migration_service(settings).migrate()
    print(f"Migrated {changed} state keys; identities and balances preserved")
