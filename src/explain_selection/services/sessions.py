"""Use case: summarise the live interactive sessions for the ``sessions`` command.

Summaries deliberately omit the registry token; they are meant to be printed.
"""

from dataclasses import dataclass
from typing import Final

from explain_selection.domain import LiveSession, Pid, SessionStatus, Target
from explain_selection.services.send import SendDeps
from explain_selection.services.targets import live_targets

# Mirrors the chooser's order in the domain: idle sessions first, then busy, then waiting.
_STATUS_ORDER: Final[dict[SessionStatus, int]] = {
    SessionStatus.IDLE: 0,
    SessionStatus.BUSY: 1,
    SessionStatus.WAITING: 2,
}


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """One live interactive session as the CLI shows it."""

    pid: Pid
    status: SessionStatus
    label: str
    cwd: str
    registered: bool


def list_sessions(deps: SendDeps) -> tuple[SessionSummary, ...]:
    """Live interactive sessions in chooser order: idle, busy, waiting, then name, cwd, pid."""
    targets = live_targets(deps.sessions, deps.registry, deps.probe)
    return tuple(_summarise(t) for t in sorted(targets, key=_chooser_order))


def _summarise(target: Target) -> SessionSummary:
    session = target.session
    return SessionSummary(
        pid=session.pid,
        status=session.status,
        label=_label(session),
        cwd=session.cwd,
        registered=target.entry is not None,
    )


def _label(session: LiveSession) -> str:
    return session.name or session.cwd.rsplit("/", 1)[-1] or session.cwd


def _chooser_order(target: Target) -> tuple[int, str, str, int]:
    session = target.session
    return (_STATUS_ORDER[session.status], session.name or "", session.cwd, session.pid)


__all__ = ["SessionSummary", "list_sessions"]
