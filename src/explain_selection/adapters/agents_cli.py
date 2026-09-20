"""``SessionLister`` backed by ``claude agents --json``.

Parses the CLI's JSON at the boundary with pydantic, keeps only process-alive interactive
sessions, and converts them to :class:`LiveSession`. Unknown or missing status is treated as
busy so an ambiguous session is never mistaken for idle.
"""

import logging
from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.domain import (
    LiveSession,
    Pid,
    SessionId,
    SessionKind,
    SessionStatus,
)
from explain_selection.errors import AgentsQueryError

logger = logging.getLogger(__name__)


class _AgentModel(BaseModel):
    """One agent object as emitted by ``claude agents --json``; unknown fields ignored."""

    model_config = ConfigDict(extra="ignore")

    pid: int | None = None
    cwd: str = ""
    kind: str = ""
    started_at: int | str | None = Field(default=None, alias="startedAt")
    session_id: str | None = Field(default=None, alias="sessionId")
    name: str | None = None
    status: str | None = None


class _AgentsEnvelope(BaseModel):
    """The ``{"agents": [...]}`` shape, when the CLI wraps the list."""

    model_config = ConfigDict(extra="ignore")

    agents: list[_AgentModel]


# Built once: constructing the adapter compiles the schema and does no I/O.
_AGENTS_ADAPTER: Final[TypeAdapter[list[_AgentModel] | _AgentsEnvelope]] = TypeAdapter(
    list[_AgentModel] | _AgentsEnvelope
)


def _started_at_ms(value: int | str | None) -> int:
    """Coerce the ``startedAt`` field to epoch milliseconds; unknown becomes 0."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value:
        try:
            return int(datetime.fromisoformat(value).timestamp() * 1000)
        except ValueError:
            return 0
    return 0


def _status(raw: str | None) -> SessionStatus:
    match raw:
        case "idle":
            return SessionStatus.IDLE
        case "waiting":
            return SessionStatus.WAITING
        case _:
            return SessionStatus.BUSY


def _to_session(model: _AgentModel, pid: Pid) -> LiveSession:
    return LiveSession(
        pid=pid,
        cwd=model.cwd,
        kind=SessionKind.INTERACTIVE,
        started_at_ms=_started_at_ms(model.started_at),
        status=_status(model.status),
        session_id=SessionId(model.session_id) if model.session_id else None,
        name=model.name,
    )


class AgentsCli:
    """Lists interactive sessions by shelling out to the ``claude`` binary."""

    def __init__(
        self, runner: CommandRunner, *, claude_bin: str = "claude", timeout_s: float = 5.0
    ) -> None:
        self._runner = runner
        self._claude_bin = claude_bin
        self._timeout_s = timeout_s

    def list_interactive(self) -> tuple[LiveSession, ...]:
        result = self._runner.run([self._claude_bin, "agents", "--json"], timeout=self._timeout_s)
        if result.returncode != 0:
            raise AgentsQueryError(f"claude agents --json exited {result.returncode}")
        try:
            parsed = _AGENTS_ADAPTER.validate_json(result.stdout)
        except ValidationError as exc:
            raise AgentsQueryError("claude agents --json had an unexpected shape") from exc
        models = parsed.agents if isinstance(parsed, _AgentsEnvelope) else parsed
        sessions: list[LiveSession] = []
        for model in models:
            if model.pid is None or model.kind != "interactive":
                continue
            sessions.append(_to_session(model, Pid(model.pid)))
        return tuple(sessions)


__all__ = ["AgentsCli"]
