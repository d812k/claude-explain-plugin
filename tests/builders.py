"""Plain builder functions for test data. No fixtures, no magic."""

from explain_selection.domain import (
    ClaudeFacts,
    DoctorFacts,
    FileFacts,
    InboundPolicy,
    InboxToken,
    LiveSession,
    MacFacts,
    Pid,
    RegistryEntry,
    RuntimeFacts,
    SessionFacts,
    SessionId,
    SessionKind,
    SessionStatus,
)

FAKE_TOKEN = InboxToken("not-a-real-token")
PLUGIN_ROOT = "/plugins/explain-selection"
VERSION = "0.1.0"


def session(
    pid: int,
    *,
    status: SessionStatus = SessionStatus.IDLE,
    kind: SessionKind = SessionKind.INTERACTIVE,
    cwd: str = "/work",
    name: str | None = None,
) -> LiveSession:
    """A process-alive session as ``claude agents --json`` would report it."""
    return LiveSession(
        pid=Pid(pid),
        cwd=cwd,
        kind=kind,
        started_at_ms=1_700_000_000_000 + pid,
        status=status,
        session_id=SessionId(f"session-{pid}"),
        name=name,
    )


def entry(
    pid: int,
    *,
    tty: str | None = None,
    tmux_pane: str | None = None,
    cwd: str = "/work",
    socket: str | None = None,
) -> RegistryEntry:
    """A registry entry as the SessionStart hook would write it."""
    return RegistryEntry(
        session_id=SessionId(f"session-{pid}"),
        pid=Pid(pid),
        cwd=cwd,
        tty=tty,
        name=None,
        socket=socket or f"/run/user/501/cc-socks/{pid}.sock",
        token=FAKE_TOKEN,
        tmux="/tmp/tmux-501/default,1234,0" if tmux_pane else None,
        tmux_pane=tmux_pane,
        registered_at_ms=1_700_000_000_000,
    )


def file_facts(
    *,
    exists: bool = True,
    mode: int | None = 0o600,
    is_dir: bool = False,
    is_socket: bool = False,
    is_executable: bool = False,
) -> FileFacts:
    """What the doctor learns about one path; a plain regular file by default."""
    return FileFacts(
        exists=exists,
        mode=mode if exists else None,
        is_dir=is_dir,
        is_socket=is_socket,
        is_executable=is_executable,
    )


MISSING_FILE = file_facts(exists=False)
PRIVATE_DIR = file_facts(mode=0o700, is_dir=True)
PRIVATE_SOCKET = file_facts(mode=0o600, is_socket=True)
SHIM = file_facts(mode=0o700, is_executable=True)


HEALTHY_RUNTIME = RuntimeFacts(
    home=PRIVATE_DIR,
    venv_python=SHIM,
    installed_version=VERSION,
    plugin_version=VERSION,
    shim=SHIM,
    shim_plugin_root=PLUGIN_ROOT,
    plugin_root=PLUGIN_ROOT,
    config_present=True,
    template_present=True,
    template_has_placeholder=True,
)


def session_facts(
    pid: int,
    *,
    kind: SessionKind = SessionKind.INTERACTIVE,
    registered: bool = True,
    socket: FileFacts | None = PRIVATE_SOCKET,
    age_ms: int = 300_000,
) -> SessionFacts:
    """One idle live session as the doctor sees it; registered with a private socket by default.

    Use :func:`dataclasses.replace` for the status and the tmux name.
    """
    return SessionFacts(
        pid=Pid(pid),
        status=SessionStatus.IDLE,
        kind=kind,
        registered=registered,
        tmux=None,
        socket=socket if registered else None,
        age_ms=age_ms,
    )


def claude_facts(
    *,
    sessions: tuple[SessionFacts, ...] = (),
    stale_entries: int = 0,
    cross_session_inbound: InboundPolicy | None = None,
    plugin_enabled: bool = True,
    agents_error: str | None = None,
) -> ClaudeFacts:
    """A healthy Claude Code side: plugin enabled, default inbound policy, no sessions."""
    return ClaudeFacts(
        sessions=sessions,
        stale_entries=stale_entries,
        cross_session_inbound=cross_session_inbound,
        plugin_enabled=plugin_enabled,
        agents_error=agents_error,
    )


def mac_facts(
    *,
    bundle: FileFacts = PRIVATE_DIR,
    shortcut_status: str | None = '{ "(null) - Explain selection - runWorkflowAsService" = { '
    '"key_equivalent" = "@~e"; }; }',
    osascript_found: bool = True,
) -> MacFacts:
    """A healthy macOS side: bundle installed, shortcut assigned, osascript present."""
    return MacFacts(bundle=bundle, shortcut_status=shortcut_status, osascript_found=osascript_found)


def doctor_facts(
    *,
    runtime: RuntimeFacts | None = None,
    claude: ClaudeFacts | None = None,
    mac: MacFacts | None = None,
) -> DoctorFacts:
    """Everything healthy on a non-macOS box unless a part is replaced."""
    return DoctorFacts(
        runtime=runtime if runtime is not None else HEALTHY_RUNTIME,
        claude=claude if claude is not None else claude_facts(),
        mac=mac,
    )
