"""Use case: record (or remove) a session's registry entry from a hook.

Runs from the SessionStart, CwdChanged and SessionEnd hooks. The session's inbox socket path
and token arrive in the environment; the Claude Code pid is read from the socket path, never
from a process-tree walk. The controlling tty is looked up for that pid. SessionEnd falls back
to the hook's ``session_id`` when the socket is not exported.
"""

from dataclasses import dataclass

from explain_selection.domain import (
    InboxToken,
    RegistryEntry,
    SessionId,
    pid_from_socket_path,
)
from explain_selection.services.protocols import Clock, RegistryStore, TtyLookup


@dataclass(frozen=True, slots=True)
class HookContext:
    """The inputs a hook hands to the register use case, already read from stdin and env."""

    session_id: SessionId | None
    cwd: str | None
    name: str | None
    socket_path: str | None
    token: InboxToken | None
    tmux: str | None
    tmux_pane: str | None


@dataclass(frozen=True, slots=True)
class RegisterDeps:
    """Everything :func:`register_session` and :func:`unregister_session` need."""

    clock: Clock
    registry: RegistryStore
    tty_lookup: TtyLookup


@dataclass(frozen=True, slots=True)
class Registered:
    """The entry was written."""

    entry: RegistryEntry


@dataclass(frozen=True, slots=True)
class Skipped:
    """No entry was written; ``reason`` says why (never contains the token)."""

    reason: str


RegisterResult = Registered | Skipped


def register_session(ctx: HookContext, deps: RegisterDeps) -> RegisterResult:
    """Write the registry entry for this session, or skip when it cannot be reached later."""
    if not ctx.socket_path:
        return Skipped("no messaging socket in environment")
    pid = pid_from_socket_path(ctx.socket_path)
    if pid is None:
        return Skipped("socket path is not a cc-socks path")
    if not ctx.token:
        return Skipped("no messaging token in environment")
    entry = RegistryEntry(
        session_id=ctx.session_id,
        pid=pid,
        cwd=ctx.cwd or "",
        tty=deps.tty_lookup.tty_for(pid),
        name=ctx.name,
        socket=ctx.socket_path,
        token=ctx.token,
        tmux=ctx.tmux,
        tmux_pane=ctx.tmux_pane,
        registered_at_ms=deps.clock.now_ms(),
    )
    deps.registry.save(entry)
    return Registered(entry)


def unregister_session(ctx: HookContext, deps: RegisterDeps) -> RegisterResult:
    """Remove this session's entry on SessionEnd, by socket pid or, failing that, session id.

    Claude Code does not export the messaging socket to the SessionEnd hook, so the pid is
    usually unknown here; the entry is then found by the ``session_id`` recorded at register.
    """
    pid = pid_from_socket_path(ctx.socket_path) if ctx.socket_path else None
    if pid is not None:
        deps.registry.delete(pid)
        return Skipped(f"entry removed for pid {pid}")
    if ctx.session_id is None:
        return Skipped("no messaging socket or session id to identify the entry")
    stale = [e.pid for e in deps.registry.read_all() if e.session_id == ctx.session_id]
    if not stale:
        return Skipped("no entry recorded for this session id")
    for entry_pid in stale:
        deps.registry.delete(entry_pid)
    return Skipped(f"entry removed for pid {', '.join(str(p) for p in stale)}")


__all__ = [
    "HookContext",
    "RegisterDeps",
    "RegisterResult",
    "Registered",
    "Skipped",
    "register_session",
    "unregister_session",
]
