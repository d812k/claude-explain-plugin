"""TmuxAwareFocus adds the active tmux pane to the frontmost terminal's tty."""

from explain_selection.adapters import CommandResult, OsascriptFocus, TmuxAwareFocus, TmuxPanes
from explain_selection.domain import Focus
from tests.fakes import FakeFocus, FakePanes, FakeRunner

CLIENTS = "/dev/ttys006\twork\n"
PANES = "0\t%3\n1\t%7\n"


def _ok(stdout: str) -> CommandResult:
    return CommandResult(returncode=0, stdout=stdout, stderr="")


def test_fills_the_pane_through_real_adapters_on_fake_runners() -> None:
    runner = FakeRunner(queue=[_ok("ttys006\n"), _ok(CLIENTS), _ok(PANES)])
    focus = TmuxAwareFocus(OsascriptFocus(runner), TmuxPanes(runner)).probe()
    assert focus == Focus(terminal_tty="ttys006", tmux_pane="%7")


def test_asks_tmux_with_the_device_path_of_the_tty() -> None:
    panes = FakePanes(pane="%2")
    TmuxAwareFocus(FakeFocus(Focus(terminal_tty="ttys003", tmux_pane=None)), panes).probe()
    assert panes.seen == ["/dev/ttys003"]


def test_keeps_an_already_absolute_tty_path() -> None:
    panes = FakePanes(pane=None)
    TmuxAwareFocus(FakeFocus(Focus(terminal_tty="/dev/pts/2", tmux_pane=None)), panes).probe()
    assert panes.seen == ["/dev/pts/2"]


def test_without_a_tty_tmux_is_not_consulted() -> None:
    panes = FakePanes(pane="%2")
    focus = TmuxAwareFocus(FakeFocus(), panes).probe()
    assert focus == Focus(terminal_tty=None, tmux_pane=None)
    assert panes.seen == []


def test_no_matching_tmux_client_leaves_the_pane_empty() -> None:
    panes = FakePanes(pane=None)
    focus = TmuxAwareFocus(FakeFocus(Focus(terminal_tty="ttys003", tmux_pane=None)), panes).probe()
    assert focus == Focus(terminal_tty="ttys003", tmux_pane=None)


def test_tmux_failure_keeps_the_tty_only_focus() -> None:
    panes = FakePanes(pane="%2", fail=True)
    focus = TmuxAwareFocus(FakeFocus(Focus(terminal_tty="ttys003", tmux_pane=None)), panes).probe()
    assert focus == Focus(terminal_tty="ttys003", tmux_pane=None)
