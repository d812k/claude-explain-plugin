"""Core data types: identifiers, live sessions and registry entries."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Final, NewType

Pid = NewType("Pid", int)
SessionId = NewType("SessionId", str)
InboxToken = NewType("InboxToken", str)

REGISTRY_FORMAT_VERSION: Final[int] = 1


class SessionKind(Enum):
    """How a Claude Code session was started."""

    INTERACTIVE = "interactive"
    BACKGROUND = "background"


class SessionStatus(Enum):
    """Whether a session is idle, running a turn, or blocked on a prompt."""

    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"


@dataclass(frozen=True, slots=True)
class LiveSession:
    """One process-alive session as reported by ``claude agents --json``.

    ``session_id`` and ``name`` are conditional in that output, hence optional here.
    """

    pid: Pid
    cwd: str
    kind: SessionKind
    started_at_ms: int
    status: SessionStatus
    session_id: SessionId | None
    name: str | None


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    """What the SessionStart hook records about a session (format version 1)."""

    session_id: SessionId
    pid: Pid
    cwd: str
    tty: str | None
    name: str | None
    socket: str
    token: InboxToken = field(repr=False)
    tmux: str | None
    tmux_pane: str | None
    registered_at_ms: int
    version: int = REGISTRY_FORMAT_VERSION


__all__ = [
    "REGISTRY_FORMAT_VERSION",
    "InboxToken",
    "LiveSession",
    "Pid",
    "RegistryEntry",
    "SessionId",
    "SessionKind",
    "SessionStatus",
]
