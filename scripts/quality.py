"""Run the quality gate on Windows, Linux or macOS without shell scripts."""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_COMMANDS = (
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
        "scripts/repair_market_diversity.py",
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
        "scripts/repair_market_diversity.py",
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
        "scripts/repair_market_diversity.py",
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
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-fail-under=100",
        "--durations=20",
    ),
    (sys.executable, "-m", "compileall", "-q", "app", "main.py"),
)
FRONTEND_COMMANDS = (
    ("node", "--test", "frontend/*.test.mjs"),
    ("node", "node_modules/eslint/bin/eslint.js", "frontend"),
    (
        "node",
        "node_modules/stylelint/bin/stylelint.mjs",
        "frontend/**/*.css",
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
)


def selected_commands(arguments: list[str]) -> tuple[tuple[str, ...], ...]:
    """Select one bounded area or preserve the combined local quality gate."""
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--python", action="store_true")
    selection.add_argument("--frontend", action="store_true")
    options = parser.parse_args(arguments)
    if options.python:
        return PYTHON_COMMANDS
    if options.frontend:
        return FRONTEND_COMMANDS
    return PYTHON_COMMANDS + FRONTEND_COMMANDS


def main(arguments: list[str] | None = None) -> None:
    """Run selected commands in order and stop at the first failed tool."""
    for command in selected_commands(arguments or []):
        print("Running:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=PROJECT_ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main(sys.argv[1:])
