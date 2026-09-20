"""Plain builder functions for test data. No fixtures, no magic."""

from explain_selection.domain import (
    InboxToken,
    LiveSession,
    Pid,
    RegistryEntry,
    SessionId,
    SessionKind,
    SessionStatus,
)

FAKE_TOKEN = InboxToken("not-a-real-token")


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
