"""The bin/ wrappers are executable POSIX sh scripts that exec their Python entrypoint."""

import os
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
BOOTSTRAP = REPO / "scripts" / "bootstrap.sh"
SCRIPTS = (*(BIN / name for name in WRAPPERS), BOOTSTRAP)
SCRIPT_IDS = (*WRAPPERS, BOOTSTRAP.name)


def _entrypoint(name: str) -> str:
    return "cli" if name == CLI_WRAPPER else name.removeprefix("explain-selection-")


@pytest.mark.parametrize("path", SCRIPTS, ids=SCRIPT_IDS)
def test_script_is_an_executable_sh_script(path: Path) -> None:
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


@pytest.mark.parametrize("path", SCRIPTS, ids=SCRIPT_IDS)
def test_script_has_no_bashisms(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "[[" not in text
    assert "function " not in text
    assert "local " not in text


def test_bootstrap_requires_uv_and_says_how_to_get_it() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "command -v uv" in text
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in text
    assert ">&2" in text
    assert "exit 1" in text


def test_bootstrap_prepares_the_venv_under_the_runtime_home_and_execs_install() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'home="${EXPLAIN_SELECTION_HOME:-$HOME/.claude/explain-selection}"' in text
    assert 'chmod 700 "$home"' in text
    assert 'uv venv --python 3.12 "$home/venv"' in text
    assert 'uv pip install --python "$home/venv/bin/python" --quiet "$root"' in text
    assert (
        'exec "$home/venv/bin/python" -m explain_selection.entrypoints.cli install '
        '--plugin-root "$root" "$@"' in text
    )


def test_bootstrap_dry_run_without_a_venv_only_prints_the_plan() -> None:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert '"$arg" = "--dry-run"' in text
    assert "[planned] venv: would create $home/venv with uv venv --python 3.12" in text
    assert "[planned] package: would install $root into the venv" in text
    assert "[planned] install: would run explain-selection install --dry-run" in text
    assert text.index("[planned] venv") < text.index("command -v uv")


def test_cli_wrapper_usage_lists_every_subcommand() -> None:
    usage = "\n".join((BIN / CLI_WRAPPER).read_text(encoding="utf-8").splitlines()[1:3])
    for command in ("version", "sessions", "send", "install", "doctor"):
        assert command in usage


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
@pytest.mark.parametrize("path", SCRIPTS, ids=SCRIPT_IDS)
def test_script_parses_as_posix_sh(path: Path) -> None:
    subprocess.run(["sh", "-n", str(path)], check=True, timeout=10)


@pytest.mark.slow
def test_bootstrap_dry_run_creates_nothing_when_there_is_no_venv(tmp_path: Path) -> None:
    home = tmp_path / "home"
    env = {**os.environ, "EXPLAIN_SELECTION_HOME": str(home)}
    result = subprocess.run(
        ["sh", str(BOOTSTRAP), "--dry-run"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert (result.returncode, result.stderr) == (0, "")
    assert result.stdout.splitlines() == [
        f"[planned] venv: would create {home}/venv with uv venv --python 3.12",
        f"[planned] package: would install {REPO} into the venv",
        "[planned] install: would run explain-selection install --dry-run",
    ]
    assert not home.exists()
