"""macOS AppleScript adapters: frontmost terminal tty, a chooser, and notifications.

All three run ``osascript`` through the injected runner, so they are unit-tested by feeding the
runner canned output. The AppleScript itself is macOS-only and is exercised for real only on a
Mac; the logic that turns its output into domain values is what the unit tests cover.
"""

from collections.abc import Sequence
from typing import Final

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.domain import Focus, Target, describe_target

_FRONTMOST_TTY_SCRIPT: Final[str] = (
    'tell application "System Events" to set frontApp '
    "to name of first process whose frontmost is true\n"
    'if frontApp is "iTerm2" then\n'
    '  tell application "iTerm2" to return tty of current session of current window\n'
    'else if frontApp is "Terminal" then\n'
    '  tell application "Terminal" to return tty of selected tab of front window\n'
    "end if\n"
    'return ""'
)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _choose_script(labels: Sequence[str]) -> str:
    items = ", ".join(f'"{_escape(label)}"' for label in labels)
    return (
        f"set chosen to choose from list {{{items}}} "
        'with prompt "Send the selection to which session?"\n'
        "if chosen is false then\n"
        '  return ""\n'
        "else\n"
        "  return item 1 of chosen\n"
        "end if"
    )


class OsascriptFocus:
    """Reports the tty of the frontmost supported terminal; tmux pane is left to the caller."""

    def __init__(self, runner: CommandRunner, *, timeout_s: float = 2.0) -> None:
        self._runner = runner
        self._timeout_s = timeout_s

    def probe(self) -> Focus:
        result = self._runner.run(
            ["osascript", "-e", _FRONTMOST_TTY_SCRIPT], timeout=self._timeout_s
        )
        if result.returncode != 0:
            return Focus(terminal_tty=None, tmux_pane=None)
        tty = result.stdout.strip()
        return Focus(terminal_tty=tty or None, tmux_pane=None)


class OsascriptChooser:
    """Presents the targets in a native list and maps the chosen label back to a target."""

    def __init__(self, runner: CommandRunner, *, timeout_s: float = 120.0) -> None:
        self._runner = runner
        self._timeout_s = timeout_s

    def choose(self, options: tuple[Target, ...]) -> Target | None:
        if not options:
            return None
        labels = [describe_target(option) for option in options]
        result = self._runner.run(
            ["osascript", "-e", _choose_script(labels)], timeout=self._timeout_s
        )
        if result.returncode != 0:
            return None
        picked = result.stdout.strip()
        if not picked:
            return None
        for option, label in zip(options, labels, strict=True):
            if label == picked:
                return option
        return None


class OsascriptNotifier:
    """Shows a macOS notification, best effort; failures are swallowed."""

    def __init__(self, runner: CommandRunner, *, timeout_s: float = 5.0) -> None:
        self._runner = runner
        self._timeout_s = timeout_s

    def notify(self, title: str, message: str) -> None:
        script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
        self._runner.run(["osascript", "-e", script], timeout=self._timeout_s)


__all__ = ["OsascriptChooser", "OsascriptFocus", "OsascriptNotifier"]
