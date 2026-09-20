"""TmuxPanes maps a client tty to the active pane of its tmux session."""

from explain_selection.adapters import CommandResult, TmuxPanes
from tests.fakes import FakeRunner

CLIENTS = "/dev/ttys006\twork\n/dev/ttys009\tother\n"
PANES = "0\t%3\n1\t%7\n0\t%8\n"


def _ok(stdout: str) -> CommandResult:
    return CommandResult(returncode=0, stdout=stdout, stderr="")


def test_returns_the_active_pane_for_the_matching_client() -> None:
    runner = FakeRunner(queue=[_ok(CLIENTS), _ok(PANES)])
    assert TmuxPanes(runner).active_pane_for_tty("/dev/ttys006") == "%7"


def test_looks_up_panes_for_the_matched_session() -> None:
    runner = FakeRunner(queue=[_ok(CLIENTS), _ok(PANES)])
    TmuxPanes(runner).active_pane_for_tty("/dev/ttys006")
    assert runner.calls[1] == (
        "tmux",
        "list-panes",
        "-t",
        "work",
        "-F",
        "#{pane_active}\t#{pane_id}",
    )


def test_no_client_for_the_tty_is_none() -> None:
    runner = FakeRunner(queue=[_ok(CLIENTS)])
    assert TmuxPanes(runner).active_pane_for_tty("/dev/ttys999") is None


def test_no_active_pane_is_none() -> None:
    runner = FakeRunner(queue=[_ok(CLIENTS), _ok("0\t%3\n0\t%8\n")])
    assert TmuxPanes(runner).active_pane_for_tty("/dev/ttys006") is None


def test_list_clients_failure_is_none() -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr="no server")])
    assert TmuxPanes(runner).active_pane_for_tty("/dev/ttys006") is None
