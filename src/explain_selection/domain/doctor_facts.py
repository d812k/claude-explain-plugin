"""What the doctor looks at: frozen facts gathered by the services, judged by ``doctor``.

Nothing here touches a file, a socket or a process; the services build these from their
adapters and hand them to :func:`explain_selection.domain.doctor.evaluate`.
"""

from dataclasses import dataclass
from typing import Literal

from explain_selection.domain.models import Pid, SessionKind, SessionStatus

type InboundPolicy = Literal["accept", "hold", "refuse"]


@dataclass(frozen=True, slots=True)
class FileFacts:
    """What ``stat`` says about one path; ``mode`` holds the permission bits only."""

    exists: bool
    mode: int | None
    is_dir: bool
    is_socket: bool
    is_executable: bool


@dataclass(frozen=True, slots=True)
class RuntimeFacts:
    """The runtime home: venv, shim, config and prompt template, plus the plugin's version."""

    home: FileFacts
    venv_python: FileFacts
    installed_version: str | None
    plugin_version: str
    shim: FileFacts
    shim_plugin_root: str | None
    plugin_root: str
    config_present: bool
    template_path: str
    template_present: bool
    template_has_placeholder: bool


@dataclass(frozen=True, slots=True)
class SessionFacts:
    """One live session; ``socket`` describes the registered inbox socket, if any."""

    pid: Pid
    status: SessionStatus
    kind: SessionKind
    registered: bool
    tmux: str | None
    socket: FileFacts | None
    age_ms: int


@dataclass(frozen=True, slots=True)
class ClaudeFacts:
    """Claude Code's side: live sessions, registry hygiene, settings and the agents query."""

    sessions: tuple[SessionFacts, ...]
    stale_entries: int
    cross_session_inbound: InboundPolicy | None
    plugin_enabled: bool
    agents_error: str | None


@dataclass(frozen=True, slots=True)
class MacFacts:
    """The macOS pieces: the Services bundle, its shortcut status and ``osascript``."""

    bundle: FileFacts
    shortcut_status: str | None
    osascript_found: bool


@dataclass(frozen=True, slots=True)
class DoctorFacts:
    """Everything the doctor looks at; ``mac`` is ``None`` off macOS."""

    runtime: RuntimeFacts
    claude: ClaudeFacts
    mac: MacFacts | None


__all__ = [
    "ClaudeFacts",
    "DoctorFacts",
    "FileFacts",
    "InboundPolicy",
    "MacFacts",
    "RuntimeFacts",
    "SessionFacts",
]
