"""CLI interpreter selection preserves explicitly activated environments."""

import os
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

import main as entrypoint


def test_entrypoint_selects_local_environment_before_application_import():
    with (
        patch.object(entrypoint.sys, "prefix", "system"),
        patch.object(entrypoint.sys, "base_prefix", "system"),
        patch.object(entrypoint.sys, "argv", ["main.py", "--role", "runtime"]),
        patch.object(Path, "is_file", return_value=True),
        patch.object(
            entrypoint, "run_local_environment", side_effect=SystemExit(23)
        ) as run,
    ):
        with pytest.raises(SystemExit) as result:
            entrypoint.main()
        assert result.value.code == 23
        executable, script = run.call_args.args
        expected = (
            Path(entrypoint.__file__).parent
            / ".venv"
            / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        assert Path(executable) == expected
        assert script == Path(entrypoint.__file__).resolve()


@pytest.mark.parametrize(
    "active_venv, local_exists", [(True, True), (False, False)]
)
def test_entrypoint_preserves_active_or_only_available_interpreter(
    active_venv,
    local_exists,
):
    with (
        patch.object(
            entrypoint.sys, "prefix", "venv" if active_venv else "system"
        ),
        patch.object(entrypoint.sys, "base_prefix", "system"),
        patch.object(entrypoint.sys, "argv", ["main.py", "--role", "runtime"]),
        patch.object(Path, "is_file", return_value=local_exists),
        patch.object(entrypoint, "run_local_environment") as replace,
        patch("app.launcher.run_role", new=AsyncMock(return_value=0)) as role,
    ):
        with pytest.raises(SystemExit) as result:
            entrypoint.main()
        assert result.value.code == 0
        replace.assert_not_called()
        role.assert_awaited_once_with("runtime")


@pytest.mark.parametrize(
    "interrupted, stuck", [(False, False), (True, False), (True, True)]
)
def test_local_interpreter_is_waited_for_and_has_bounded_shutdown(
    interrupted, stuck
):
    process = Mock()
    process.wait.side_effect = (
        ([KeyboardInterrupt()] if interrupted else [])
        + ([subprocess.TimeoutExpired("python", 20)] if stuck else [])
        + [7]
    )
    with (
        patch.object(entrypoint.sys, "argv", ["main.py", "--role", "runtime"]),
        patch.object(
            entrypoint.subprocess, "Popen", return_value=process
        ) as start,
    ):
        with pytest.raises(SystemExit) as result:
            entrypoint.run_local_environment(Path("python"), Path("main.py"))
        assert result.value.code == 7
        start.assert_called_once_with(
            ["python", "main.py", "--role", "runtime"]
        )
        assert process.terminate.call_count == int(stuck)
        if interrupted:
            assert process.wait.call_args_list[1].kwargs == {"timeout": 20}
