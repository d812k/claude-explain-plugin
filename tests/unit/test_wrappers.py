"""The bin/ wrappers are executable POSIX sh scripts that exec their Python entrypoint."""

import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BIN = REPO / "bin"
WRAPPERS = (
    "explain-selection-register",
    "explain-selection-unregister",
    "explain-selection-capture",
    "explain-selection",
)
CLI_WRAPPER = "explain-selection"


def _entrypoint(name: str) -> str:
    return "cli" if name == CLI_WRAPPER else name.removeprefix("explain-selection-")


@pytest.mark.parametrize("name", WRAPPERS)
def test_wrapper_is_an_executable_sh_script(name: str) -> None:
    path = BIN / name
    assert path.is_file()
    assert path.stat().st_mode & stat.S_IXUSR
    assert path.read_text(encoding="utf-8").splitlines()[0] == "#!/bin/sh"


@pytest.mark.parametrize("name", WRAPPERS)
def test_wrapper_execs_its_entrypoint_with_the_plugin_root(name: str) -> None:
    text = (BIN / name).read_text(encoding="utf-8")
    assert f'exec "$py" -m explain_selection.entrypoints.{_entrypoint(name)} "$@"' in text
    assert "export EXPLAIN_SELECTION_PLUGIN_ROOT" in text


@pytest.mark.parametrize("name", WRAPPERS)
def test_wrapper_resolves_the_interpreter_in_the_agreed_order(name: str) -> None:
    text = (BIN / name).read_text(encoding="utf-8")
    first = text.index("EXPLAIN_SELECTION_PYTHON")
    second = text.index(".claude/explain-selection/venv/bin/python")
    third = text.index('"$root/.venv/bin/python"')
    assert first < second < third


@pytest.mark.parametrize("name", WRAPPERS)
def test_wrapper_has_no_bashisms(name: str) -> None:
    text = (BIN / name).read_text(encoding="utf-8")
    assert "[[" not in text
    assert "function " not in text
    assert "local " not in text


def test_capture_wrapper_notifies_when_no_interpreter_is_found() -> None:
    text = (BIN / "explain-selection-capture").read_text(encoding="utf-8")
    assert "osascript -e 'display notification" in text


def test_cli_wrapper_reports_a_missing_interpreter_on_stderr_and_exits_one() -> None:
    text = (BIN / CLI_WRAPPER).read_text(encoding="utf-8")
    assert "No Python interpreter found" in text
    assert ">&2" in text
    assert "exit 1" in text
    assert "osascript" not in text
    assert "exit 0" not in text


@pytest.mark.slow
@pytest.mark.parametrize("name", WRAPPERS)
def test_wrapper_parses_as_posix_sh(name: str) -> None:
    subprocess.run(["sh", "-n", str(BIN / name)], check=True, timeout=10)
