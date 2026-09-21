"""Use case: summarise every live session, background ones included, for ``sessions``.

Summaries deliberately omit the registry token; they are meant to be printed.
"""

from dataclasses import dataclass

from explain_selection.domain import (
    LiveSession,
    Pid,
    SessionKind,
    SessionStatus,
    Target,
    chooser_order,
)
from explain_selection.services.send import SendDeps
from explain_selection.services.targets import live_targets


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One live session, of either kind, as the CLI shows it."""

    pid: Pid
    status: SessionStatus
    kind: SessionKind
    label: str
    cwd: str
    registered: bool


def list_sessions(deps: SendDeps) -> tuple[SessionSummary, ...]:
    """Every live session in chooser order: idle, busy, waiting, then name, cwd, pid."""
    targets = live_targets(deps.sessions, deps.registry, deps.probe, include_background=True)
    return tuple(_summarise(t) for t in sorted(targets, key=chooser_order))


def _summarise(target: Target) -> SessionSummary:
    session = target.session
    return SessionSummary(
        pid=session.pid,
        status=session.status,
        kind=session.kind,
        label=_label(session),
        cwd=session.cwd,
        registered=target.entry is not None,
    )


def _label(session: LiveSession) -> str:
    return session.name or session.cwd.rsplit("/", 1)[-1] or session.cwd


__all__ = ["SessionSummary", "list_sessions"]
