"""Start World Freight Idle with ``python main.py``."""

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
    """Start the local single-process application."""
    entrypoint = Path(__file__).resolve()
    local_python = (
        entrypoint.parent
        / ".venv"
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if sys.prefix == sys.base_prefix and local_python.is_file():
        run_local_environment(local_python, entrypoint)
    from app.launcher import run

    raise SystemExit(run())


if __name__ == "__main__":
    main()
