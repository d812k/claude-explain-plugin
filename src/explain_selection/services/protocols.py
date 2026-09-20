"""Adapter interfaces the use cases depend on, plus the small value objects they pass.

Every side effect the services need is expressed here as a ``Protocol``. Adapters implement
them; unit tests supply in-memory fakes. Nothing in this module performs I/O.
"""

from dataclasses import dataclass
from typing import Protocol

from explain_selection.domain import (
    Focus,
    InboxToken,
    LiveSession,
    Pid,
    RegistryEntry,
    RememberedTarget,
    Target,
)


@dataclass(frozen=True, slots=True)
class InboxAddress:
    """Where and how to reach a session's inbox socket.

    ``socket_path`` is what the registry recorded and may be stale; the poster falls back to
    the paths derived from ``pid``. ``token`` authenticates the sender; ``None`` means post as
    an unverified peer.
    """

    pid: Pid
    socket_path: str | None
    token: InboxToken | None


class Clock(Protocol):
    """The only source of wall-clock time in the services layer."""

    def now_ms(self) -> int:
        """Milliseconds since the Unix epoch."""
        ...


class SessionLister(Protocol):
    """Lists the live interactive Claude Code sessions on this machine."""

    def list_interactive(self) -> tuple[LiveSession, ...]:
        """Return the process-alive interactive sessions, in any order."""
        ...


class RegistryStore(Protocol):
    """Persists one registry entry per session."""

    def save(self, entry: RegistryEntry) -> None:
        """Write ``entry`` atomically, replacing any entry for the same pid."""
        ...

    def delete(self, pid: Pid) -> None:
        """Remove the entry for ``pid``; do nothing if it is absent."""
        ...

    def read_all(self) -> tuple[RegistryEntry, ...]:
        """Return every valid entry, skipping and logging files that fail to parse."""
        ...


class TtyLookup(Protocol):
    """Resolves the controlling terminal of a process."""

    def tty_for(self, pid: Pid) -> str | None:
        """Return the tty name for ``pid`` (for example ``ttys005``), or ``None``."""
        ...


class InboxPoster(Protocol):
    """Posts one message into a session's inbox socket."""

    def post(self, address: InboxAddress, content: str) -> None:
        """Deliver ``content``; raise :class:`InboxUnavailableError` if no socket accepts it."""
        ...


class FocusProbe(Protocol):
    """Reports where the user is currently looking, best effort."""

    def probe(self) -> Focus:
        """Return the frontmost terminal tty and tmux pane, each ``None`` when unknown."""
        ...


class Chooser(Protocol):
    """Asks the user to pick one target when selection is ambiguous."""

    def choose(self, options: tuple[Target, ...]) -> Target | None:
        """Return the chosen target, or ``None`` if the user dismissed the chooser."""
        ...


class TargetMemory(Protocol):
    """Remembers the user's last explicit target pick across hotkey presses."""

    def load(self) -> RememberedTarget | None:
        """Return the remembered pick, or ``None`` if there is none."""
        ...

    def save(self, remembered: RememberedTarget) -> None:
        """Record ``remembered`` as the latest pick."""
        ...


class LinkOpener(Protocol):
    """Opens a ``claude-cli://`` deep link, spawning a new Claude Code window."""

    def open(self, url: str) -> None:
        """Hand ``url`` to the OS opener."""
        ...


class TempFileWriter(Protocol):
    """Writes an oversized selection to a temp file for the mode A fallback."""

    def write(self, text: str) -> str:
        """Persist ``text`` and return its absolute path."""
        ...


class Notifier(Protocol):
    """Shows a short message to the user outside the terminal."""

    def notify(self, title: str, message: str) -> None:
        """Best effort; implementations may raise, callers must not."""
        ...


__all__ = [
    "Chooser",
    "Clock",
    "FocusProbe",
    "InboxAddress",
    "InboxPoster",
    "LinkOpener",
    "Notifier",
    "RegistryStore",
    "SessionLister",
    "TargetMemory",
    "TempFileWriter",
    "TtyLookup",
]
