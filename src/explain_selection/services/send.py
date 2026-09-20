"""Use case: post a message, unchanged, into one live session named by pid.

This backs the ``explain-selection send`` command. Unlike delivery there is no prompt
template: the receiving Claude Code already frames inbox messages as coming from another
session, so the text is posted verbatim.
"""

from dataclasses import dataclass

from explain_selection.domain import Pid, Target
from explain_selection.errors import InboxUnavailableError
from explain_selection.services.protocols import (
    InboxPoster,
    ProcessProbe,
    RegistryStore,
    SessionLister,
)
from explain_selection.services.targets import address_for, live_targets


@dataclass(frozen=True, slots=True)
class SendDeps:
    """Every side effect sending and listing sessions need, injected once."""

    sessions: SessionLister
    registry: RegistryStore
    poster: InboxPoster
    probe: ProcessProbe


@dataclass(frozen=True, slots=True)
class Sent:
    """The message reached the session's inbox."""

    target: Target
    chars: int


@dataclass(frozen=True, slots=True)
class NoSuchSession:
    """No live interactive session has this pid."""

    pid: Pid


@dataclass(frozen=True, slots=True)
class Unavailable:
    """The session is live but no inbox socket accepted the message."""

    pid: Pid
    reason: str


SendResult = Sent | NoSuchSession | Unavailable


def send_message(pid: Pid, content: str, deps: SendDeps) -> SendResult:
    """Post ``content`` verbatim into the live interactive session ``pid``."""
    matches = [
        t for t in live_targets(deps.sessions, deps.registry, deps.probe) if t.session.pid == pid
    ]
    if not matches:
        return NoSuchSession(pid)
    target = matches[0]
    try:
        deps.poster.post(address_for(target), content)
    except InboxUnavailableError as error:
        return Unavailable(pid, str(error))
    return Sent(target, len(content))


__all__ = ["NoSuchSession", "SendDeps", "SendResult", "Sent", "Unavailable", "send_message"]
