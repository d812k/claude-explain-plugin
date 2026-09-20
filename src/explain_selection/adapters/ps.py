"""``TtyLookup`` backed by ``ps``.

``ps -o tty= -p <pid>`` prints the controlling terminal of a process (for example ``ttys005``
on macOS or ``pts/2`` on Linux) or a placeholder when there is none. We shell out only to learn
the tty; the pid itself comes from the socket path.
"""

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.domain import Pid

_NO_TTY = frozenset({"", "?", "??", "-"})


class PsTtyLookup:
    """Resolves a process's tty via ``ps``."""

    def __init__(self, runner: CommandRunner, *, timeout_s: float = 2.0) -> None:
        self._runner = runner
        self._timeout_s = timeout_s

    def tty_for(self, pid: Pid) -> str | None:
        result = self._runner.run(["ps", "-o", "tty=", "-p", str(pid)], timeout=self._timeout_s)
        if result.returncode != 0:
            return None
        tty = result.stdout.strip()
        if tty in _NO_TTY:
            return None
        return tty


__all__ = ["PsTtyLookup"]
