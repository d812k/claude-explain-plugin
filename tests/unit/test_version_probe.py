"""VenvVersionProbe runs the venv's Python through the injected runner."""

from collections.abc import Sequence
from pathlib import Path

from explain_selection.adapters import DISTRIBUTION, CommandResult, VenvVersionProbe
from explain_selection.errors import SubprocessError
from tests.fakes import FakeRunner

PYTHON = Path("/home/me/.claude/explain-selection/venv/bin/python")


class _MissingBinaryRunner:
    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        raise SubprocessError(f"{args[0]} not found")


def test_the_version_is_read_from_importlib_metadata_in_the_given_interpreter() -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=0, stdout="0.1.0\n", stderr="")])
    assert VenvVersionProbe(runner).installed_version(PYTHON) == "0.1.0"
    assert runner.calls == [
        (
            str(PYTHON),
            "-c",
            f"import importlib.metadata as m; print(m.version({DISTRIBUTION!r}))",
        )
    ]
    assert DISTRIBUTION == "explain-selection"


def test_a_failing_command_or_empty_output_reads_as_no_version() -> None:
    failing = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr="not found")])
    assert VenvVersionProbe(failing).installed_version(PYTHON) is None
    blank = FakeRunner(queue=[CommandResult(returncode=0, stdout="\n", stderr="")])
    assert VenvVersionProbe(blank).installed_version(PYTHON) is None


def test_a_missing_interpreter_reads_as_no_version() -> None:
    assert VenvVersionProbe(_MissingBinaryRunner()).installed_version(PYTHON) is None
