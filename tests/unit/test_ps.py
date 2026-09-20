"""PsTtyLookup returns a process's tty, or None when there is none."""

import pytest

from explain_selection.adapters import CommandResult, PsTtyLookup
from explain_selection.domain import Pid
from tests.fakes import FakeRunner


def _runner(stdout: str, *, returncode: int = 0) -> FakeRunner:
    return FakeRunner(queue=[CommandResult(returncode=returncode, stdout=stdout, stderr="")])


def test_returns_the_trimmed_tty() -> None:
    assert PsTtyLookup(_runner("ttys005\n")).tty_for(Pid(10)) == "ttys005"


def test_dev_prefix_is_stripped() -> None:
    assert PsTtyLookup(_runner("/dev/ttys005\n")).tty_for(Pid(10)) == "ttys005"


def test_linux_pts_name_is_returned() -> None:
    assert PsTtyLookup(_runner("pts/2\n")).tty_for(Pid(10)) == "pts/2"


@pytest.mark.parametrize("placeholder", ["", "?\n", "??\n", "-\n"])
def test_placeholder_ttys_become_none(placeholder: str) -> None:
    assert PsTtyLookup(_runner(placeholder)).tty_for(Pid(10)) is None


def test_non_zero_exit_is_none() -> None:
    assert PsTtyLookup(_runner("", returncode=1)).tty_for(Pid(10)) is None


def test_the_command_targets_the_pid() -> None:
    runner = _runner("ttys005\n")
    PsTtyLookup(runner).tty_for(Pid(4242))
    assert runner.calls == [("ps", "-o", "tty=", "-p", "4242")]
