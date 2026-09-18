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
    ),
    (
        sys.executable,
        "-m",
        "mypy",
        "app",
        "main.py",
        "scripts/update_test_profile.py",
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
