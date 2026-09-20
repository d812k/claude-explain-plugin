"""Compose the frontmost-terminal probe with tmux so a Focus also carries the active pane.

``OsascriptFocus`` only knows the tty of the frontmost terminal window (``ttys003``). When
that terminal runs tmux, the session the user is looking at is the one in the active pane
of the tmux client attached to that tty, so the pane id is a stronger routing signal.
"""

import logging
from typing import Protocol

from explain_selection.domain import Focus
from explain_selection.errors import SubprocessError
from explain_selection.services import FocusProbe

logger = logging.getLogger(__name__)

_DEV_PREFIX = "/dev/"


class PaneLookup(Protocol):
    """Maps a client tty device path (``/dev/ttys003``) to the active pane of its session."""

    def active_pane_for_tty(self, tty: str) -> str | None:
        """Return the pane id (``%7``) or ``None`` when no tmux client uses that tty."""
        ...


class TmuxAwareFocus:
    """A FocusProbe that fills ``tmux_pane`` from the terminal tty; tmux failures are ignored."""

    def __init__(self, terminal: FocusProbe, panes: PaneLookup) -> None:
        self._terminal = terminal
        self._panes = panes

    def probe(self) -> Focus:
        focus = self._terminal.probe()
        if focus.terminal_tty is None or focus.tmux_pane is not None:
            return focus
        try:
            pane = self._panes.active_pane_for_tty(_device_path(focus.terminal_tty))
        except SubprocessError:
            logger.debug("tmux unavailable; focus keeps only the terminal tty")
            return focus
        return Focus(terminal_tty=focus.terminal_tty, tmux_pane=pane)


def _device_path(tty: str) -> str:
    return tty if tty.startswith("/") else _DEV_PREFIX + tty


__all__ = ["PaneLookup", "TmuxAwareFocus"]
