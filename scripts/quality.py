"""Run the quality gate on Windows, Linux or macOS without shell scripts."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    (
        sys.executable,
        "-m",
        "ruff",
        "check",
        "app",
        "tests",
        "main.py",
        "scripts/quality.py",
        "scripts/update_test_profile.py",
        "scripts/normalize_world_catalogue.py",
        "scripts/import_legacy_game.py",
        "scripts/upgrade_vehicle_energy.py",
        "scripts/audit_economy.py",
        "scripts/audit_routing_readiness.py",
        "scripts/repair_transport_metadata.py",
        "scripts/upgrade_market_stock.py",
    ),
    (
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        "app",
        "tests",
        "main.py",
        "scripts/quality.py",
        "scripts/update_test_profile.py",
        "scripts/normalize_world_catalogue.py",
        "scripts/import_legacy_game.py",
        "scripts/upgrade_vehicle_energy.py",
        "scripts/audit_economy.py",
        "scripts/audit_routing_readiness.py",
        "scripts/repair_transport_metadata.py",
        "scripts/upgrade_market_stock.py",
    ),
    (
        sys.executable,
        "-m",
        "mypy",
        "app",
        "main.py",
        "scripts/update_test_profile.py",
        "scripts/normalize_world_catalogue.py",
        "scripts/import_legacy_game.py",
        "scripts/upgrade_vehicle_energy.py",
        "scripts/audit_economy.py",
        "scripts/audit_routing_readiness.py",
        "scripts/repair_transport_metadata.py",
        "scripts/upgrade_market_stock.py",
    ),
    (
        "node",
        "node_modules/pyright/index.js",
        "--pythonpath",
        sys.executable,
    ),
    (
        sys.executable,
        "-m",
        "pytest",
        "tests/test_process_isolation.py::"
        "test_real_supervisor_starts_outside_repository_and_closes_children",
    ),
    (
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not supervisor_integration",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-fail-under=100",
    ),
    (
        "node",
        "--test",
        "frontend/*.test.mjs",
    ),
    ("node", "node_modules/eslint/bin/eslint.js", "frontend"),
    (
        "node",
        "node_modules/stylelint/bin/stylelint.mjs",
        "frontend/style.css",
    ),
    (
        "node",
        "node_modules/prettier/bin/prettier.cjs",
        "--check",
        "frontend",
        "*.config.js",
        "jsconfig.json",
        ".prettierrc.json",
    ),
    (
        "node",
        "node_modules/typescript/bin/tsc",
        "--project",
        "jsconfig.json",
    ),
    ("node", "node_modules/vite/bin/vite.js", "build"),
    (sys.executable, "-m", "compileall", "-q", "app", "main.py"),
)

if __name__ == "__main__":
    for command in COMMANDS:
        print("Running:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)
