"""Start World Freight Idle with ``python main.py``."""

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn


def run_local_environment(executable: Path, entrypoint: Path) -> NoReturn:
    """Wait for the local interpreter, including its Ctrl+C cleanup."""
    process = subprocess.Popen(
        [str(executable), str(entrypoint), *sys.argv[1:]]
    )
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        try:
            returncode = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.terminate()
            returncode = process.wait()
    raise SystemExit(returncode)


def main() -> None:
    """Start isolated runtime and preparation with one documented command."""
    entrypoint = Path(__file__).resolve()
    local_python = (
        entrypoint.parent
        / ".venv"
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if sys.prefix == sys.base_prefix and local_python.is_file():
        run_local_environment(local_python, entrypoint)
    from app.launcher import run_role

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role", choices=("all", "runtime", "prewarm"), default="all"
    )
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run_role(args.role)))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
