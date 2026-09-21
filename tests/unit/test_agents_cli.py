"""AgentsCli parses ``claude agents --json`` and keeps live sessions of every known kind."""

import json

import pytest

from explain_selection.adapters import AgentsCli, CommandResult
from explain_selection.domain import SessionKind, SessionStatus
from explain_selection.errors import AgentsQueryError
from tests.fakes import FakeRunner

INTERACTIVE = {
    "pid": 4242,
    "cwd": "/work/proj",
    "kind": "interactive",
    "startedAt": 1_700_000_000_000,
    "sessionId": "sid-1",
    "name": "proj",
    "status": "idle",
}
BACKGROUND = {"pid": 99, "cwd": "/bg", "kind": "background", "status": "busy"}
DEAD = {"cwd": "/gone", "kind": "interactive", "status": "idle"}


def _runner(payload: object, *, returncode: int = 0) -> FakeRunner:
    return FakeRunner(
        queue=[CommandResult(returncode=returncode, stdout=json.dumps(payload), stderr="")]
    )


def test_lists_live_sessions_of_both_kinds_and_drops_rows_without_a_pid() -> None:
    runner = _runner([INTERACTIVE, BACKGROUND, DEAD])
    sessions = AgentsCli(runner).list_live()
    assert [(s.pid, s.kind) for s in sessions] == [
        (4242, SessionKind.INTERACTIVE),
        (99, SessionKind.BACKGROUND),
    ]
    first = sessions[0]
    assert first.cwd == "/work/proj"
    assert first.status is SessionStatus.IDLE
    assert first.session_id == "sid-1"
    assert first.started_at_ms == 1_700_000_000_000


def test_rows_with_an_unknown_kind_are_skipped() -> None:
    runner = _runner([{**INTERACTIVE, "kind": "remote"}])
    assert AgentsCli(runner).list_live() == ()


def test_accepts_an_agents_envelope() -> None:
    runner = _runner({"agents": [INTERACTIVE]})
    sessions = AgentsCli(runner).list_live()
    assert [s.pid for s in sessions] == [4242]


def test_unknown_status_is_treated_as_busy() -> None:
    runner = _runner([{**INTERACTIVE, "status": "thinking"}])
    sessions = AgentsCli(runner).list_live()
    assert sessions[0].status is SessionStatus.BUSY


def test_missing_status_is_treated_as_busy() -> None:
    payload = {k: v for k, v in INTERACTIVE.items() if k != "status"}
    sessions = AgentsCli(_runner([payload])).list_live()
    assert sessions[0].status is SessionStatus.BUSY


def test_iso_started_at_is_parsed_to_millis() -> None:
    runner = _runner([{**INTERACTIVE, "startedAt": "2023-11-14T22:13:20+00:00"}])
    sessions = AgentsCli(runner).list_live()
    assert sessions[0].started_at_ms == 1_700_000_000_000


def test_non_zero_exit_raises() -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr="boom")])
    with pytest.raises(AgentsQueryError):
        AgentsCli(runner).list_live()


def test_invalid_json_raises() -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=0, stdout="not json", stderr="")])
    with pytest.raises(AgentsQueryError):
        AgentsCli(runner).list_live()


def test_the_command_is_the_agents_json_call() -> None:
    runner = _runner([])
    AgentsCli(runner, claude_bin="/opt/claude").list_live()
    assert runner.calls == [("/opt/claude", "agents", "--json")]
