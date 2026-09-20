"""The osascript adapters turn AppleScript output into domain values."""

import logging

import pytest

from explain_selection.adapters import CommandResult, OsascriptChooser, OsascriptFocus
from explain_selection.domain import describe_target, join_targets
from tests.builders import session
from tests.fakes import FakeRunner


def _runner(stdout: str, *, returncode: int = 0) -> FakeRunner:
    return FakeRunner(queue=[CommandResult(returncode=returncode, stdout=stdout, stderr="")])


def test_focus_returns_the_frontmost_tty() -> None:
    focus = OsascriptFocus(_runner("ttys003\n")).probe()
    assert focus.terminal_tty == "ttys003"
    assert focus.tmux_pane is None


def test_focus_strips_the_dev_prefix_apple_terminals_report() -> None:
    assert OsascriptFocus(_runner("/dev/ttys005\n")).probe().terminal_tty == "ttys005"


def test_focus_empty_output_is_none() -> None:
    assert OsascriptFocus(_runner("\n")).probe().terminal_tty is None


def test_focus_non_zero_exit_is_none() -> None:
    assert OsascriptFocus(_runner("", returncode=1)).probe().terminal_tty is None


def test_focus_failure_is_logged_with_exit_code_and_stderr(
    caplog: pytest.LogCaptureFixture,
) -> None:
    denied = "execution error: Not authorized to send Apple events to System Events. (-1743)"
    runner = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr=denied + "\n")])
    with caplog.at_level(logging.WARNING, logger="explain_selection"):
        OsascriptFocus(runner).probe()
    assert "exited 1" in caplog.text
    assert denied in caplog.text


def test_chooser_maps_the_chosen_label_back_to_its_target() -> None:
    options = join_targets((session(10, name="a"), session(20, name="b")), ())
    chosen_label = describe_target(options[1])
    result = OsascriptChooser(_runner(chosen_label + "\n")).choose(options)
    assert result is options[1]


def test_chooser_empty_output_means_cancelled() -> None:
    options = join_targets((session(10),), ())
    assert OsascriptChooser(_runner("")).choose(options) is None


def test_chooser_with_no_options_is_none() -> None:
    assert OsascriptChooser(_runner("anything")).choose(()) is None
