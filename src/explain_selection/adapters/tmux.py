"""tmux queries: given the terminal tty a user is looking at, find the active pane there.

A tmux client is attached to a terminal tty; that client has a session; the session has one
active pane. The active pane's id (for example ``%7``) is what a registry entry records as
``tmux_pane``, so a selection can be routed to the exact pane in view.
"""

from explain_selection.adapters.subprocess_runner import CommandRunner

_SEP = "\t"


class TmuxPanes:
    """Resolves the active tmux pane for a client tty."""

    def __init__(
        self, runner: CommandRunner, *, tmux_bin: str = "tmux", timeout_s: float = 2.0
    ) -> None:
        self._runner = runner
        self._tmux_bin = tmux_bin
        self._timeout_s = timeout_s

    def active_pane_for_tty(self, tty: str) -> str | None:
        session = self._session_for_tty(tty)
        if session is None:
            return None
        return self._active_pane(session)

    def _session_for_tty(self, tty: str) -> str | None:
        result = self._runner.run(
            [self._tmux_bin, "list-clients", "-F", f"#{{client_tty}}{_SEP}#{{client_session}}"],
            timeout=self._timeout_s,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            client_tty, _, session = line.partition(_SEP)
            if client_tty == tty and session:
                return session
        return None

    def _active_pane(self, session: str) -> str | None:
        result = self._runner.run(
            [
                self._tmux_bin,
                "list-panes",
                "-t",
                session,
                "-F",
                f"#{{pane_active}}{_SEP}#{{pane_id}}",
            ],
            timeout=self._timeout_s,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            active, _, pane_id = line.partition(_SEP)
            if active == "1" and pane_id:
                return pane_id
        return None


__all__ = ["TmuxPanes"]
