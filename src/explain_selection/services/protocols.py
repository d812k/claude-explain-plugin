"""Adapter interfaces the use cases depend on, plus the small value objects they pass.

Every side effect the services need is expressed here as a ``Protocol``. Adapters implement
them; unit tests supply in-memory fakes. Nothing in this module performs I/O.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from explain_selection.domain import (
    FileFacts,
    Focus,
    InboundPolicy,
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
    """Lists the live Claude Code sessions on this machine, of every known kind."""

    def list_live(self) -> tuple[LiveSession, ...]:
        """Return the process-alive sessions, interactive and background, in any order."""
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


class ProcessProbe(Protocol):
    """Answers whether a process still exists on this machine."""

    def is_alive(self, pid: Pid) -> bool:
        """``True`` when ``pid`` is running, including when it belongs to another user."""
        ...


class InstallFiles(Protocol):
    """The file operations the install step needs; each raises :class:`InstallError`."""

    def ensure_private_dir(self, path: Path) -> None:
        """Create ``path`` if missing and make it mode 0700 either way."""
        ...

    def exists(self, path: Path) -> bool:
        """``True`` when a file or directory is at ``path``."""
        ...

    def write_private_file(self, path: Path, content: str, mode: int) -> None:
        """Write ``content`` to ``path`` and set ``mode``; the parent must already exist."""
        ...

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy one file, contents only."""
        ...

    def replace_tree(self, src: Path, dst: Path) -> None:
        """Copy the directory ``src`` to ``dst``, removing whatever was at ``dst`` first."""
        ...


class ServicesRegistrar(Protocol):
    """Registers a Services-menu entry's keyboard shortcut with macOS."""

    def set_shortcut(self, service_name: str, key: str) -> None:
        """Assign ``key`` (for example ``@~e``) to the workflow service ``service_name``."""
        ...

    def refresh(self) -> None:
        """Make the Services menu pick up the change."""
        ...

    def read_status(self) -> str:
        """The current Services status as macOS reports it, for verification."""
        ...


@dataclass(frozen=True, slots=True)
class ClaudeSettingsFacts:
    """What the doctor reads from Claude Code's ``settings.json`` files."""

    cross_session_inbound: InboundPolicy | None
    plugin_enabled: bool


class FileInspector(Protocol):
    """Read-only questions about paths, for the doctor."""

    def inspect(self, path: Path) -> FileFacts:
        """Describe ``path``; missing yields ``exists=False``, unstat-able ``readable=False``."""
        ...

    def read_text(self, path: Path) -> str | None:
        """The file's text, or ``None`` when it is missing or cannot be read as UTF-8 text."""
        ...


class VersionProbe(Protocol):
    """Asks an interpreter which version of this package it has installed."""

    def installed_version(self, python: Path) -> str | None:
        """The distribution version under ``python``, or ``None`` if it cannot be read."""
        ...


class ClaudeSettingsReader(Protocol):
    """Reads the Claude Code settings the doctor cares about."""

    def read(self) -> ClaudeSettingsFacts:
        """Merge the settings files; missing or invalid files count as unset."""
        ...


class MacProbe(Protocol):
    """The macOS-only facts: Services bundle, shortcut status and ``osascript``."""

    def bundle(self) -> FileFacts:
        """Describe the installed ``Explain selection.workflow`` bundle."""
        ...

    def shortcut_status(self) -> str | None:
        """The Services status as ``defaults`` reports it, or ``None`` if it cannot be read."""
        ...

    def osascript_found(self) -> bool:
        """``True`` when ``osascript`` is on ``PATH``."""
        ...


__all__ = [
    "Chooser",
    "ClaudeSettingsFacts",
    "ClaudeSettingsReader",
    "Clock",
    "FileInspector",
    "FocusProbe",
    "InboxAddress",
    "InboxPoster",
    "InstallFiles",
    "LinkOpener",
    "MacProbe",
    "Notifier",
    "ProcessProbe",
    "RegistryStore",
    "ServicesRegistrar",
    "SessionLister",
    "TargetMemory",
    "TempFileWriter",
    "TtyLookup",
    "VersionProbe",
]
