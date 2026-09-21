"""What the doctor looks at: frozen facts gathered by the services, judged by ``doctor``.

Nothing here touches a file, a socket or a process; the services build these from their
adapters and hand them to :func:`explain_selection.domain.doctor.evaluate`.
"""

from dataclasses import dataclass
from typing import Literal

from explain_selection.domain.models import Pid, SessionKind, SessionStatus

type InboundPolicy = Literal["accept", "hold", "refuse"]
type RootSource = Literal["environment", "shim", "checkout"]


@dataclass(frozen=True, slots=True)
class FileFacts:
    """What ``stat`` says about one path; ``mode`` holds the permission bits only.

    ``readable`` is ``False`` when the path is missing, or exists but could not be stat'ed
    or read; the other facts are then unknown and left at their defaults.
    """

    exists: bool
    mode: int | None
    is_dir: bool
    is_socket: bool
    is_executable: bool
    readable: bool


@dataclass(frozen=True, slots=True)
class RuntimeFacts:
    """The runtime home: venv, shim, config and prompt template, plus the plugin's version.

    ``root_source`` says which record named ``plugin_root``: the wrapper's environment export,
    the installed shim, or the source checkout the package runs from.
    """

    home: FileFacts
    venv_python: FileFacts
    installed_version: str | None
    plugin_version: str
    shim: FileFacts
    shim_plugin_root: str | None
    plugin_root: str
    root_source: RootSource
    config_present: bool
    template_path: str
    template: FileFacts
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
    unreadable_settings: tuple[str, ...]
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
    "RootSource",
    "RuntimeFacts",
    "SessionFacts",
]
