"""The sessions use case summarises every live session in chooser order, token-free."""

from dataclasses import fields

from explain_selection.domain import LiveSession, Pid, SessionKind, SessionStatus
from explain_selection.services import SendDeps, SessionSummary, list_sessions
from tests.builders import FAKE_TOKEN, entry, session
from tests.fakes import FakePoster, FakeProbe, FakeRegistry, FakeSessions


def _deps(*live: LiveSession, registered: tuple[int, ...] = ()) -> SendDeps:
    return SendDeps(
        sessions=FakeSessions(live),
        registry=FakeRegistry(entries={Pid(pid): entry(pid) for pid in registered}),
        poster=FakePoster(),
        probe=FakeProbe(),
    )


def test_summaries_describe_each_live_session_and_whether_it_is_registered() -> None:
    deps = _deps(session(10, name="alpha"), session(20, cwd="/home/me/proj"), registered=(10,))
    # An unnamed session sorts as "" and therefore ahead of "alpha", as in the chooser.
    interactive = SessionKind.INTERACTIVE
    assert list_sessions(deps) == (
        SessionSummary(Pid(20), SessionStatus.IDLE, interactive, "proj", "/home/me/proj", False),
        SessionSummary(Pid(10), SessionStatus.IDLE, interactive, "alpha", "/work", True),
    )


def test_the_label_falls_back_to_the_cwd_when_it_has_no_basename() -> None:
    (summary,) = list_sessions(_deps(session(10, cwd="/")))
    assert summary.label == "/"


def test_background_sessions_are_listed_with_their_kind() -> None:
    deps = _deps(session(10, kind=SessionKind.BACKGROUND), session(20))
    assert [(s.pid, s.kind) for s in list_sessions(deps)] == [
        (Pid(10), SessionKind.BACKGROUND),
        (Pid(20), SessionKind.INTERACTIVE),
    ]


def test_order_is_idle_busy_waiting_then_name_cwd_pid() -> None:
    deps = _deps(
        session(1, status=SessionStatus.WAITING, name="a"),
        session(2, status=SessionStatus.BUSY, name="z"),
        session(3, name="b", cwd="/x"),
        session(4, name="b", cwd="/w"),
        session(5, name="a"),
        session(6, name="b", cwd="/w"),
    )
    assert [s.pid for s in list_sessions(deps)] == [5, 4, 6, 3, 2, 1]


def test_summaries_carry_no_token() -> None:
    assert {f.name for f in fields(SessionSummary)} == {
        "pid",
        "status",
        "kind",
        "label",
        "cwd",
        "registered",
    }
    summaries = list_sessions(_deps(session(10), registered=(10,)))
    assert FAKE_TOKEN not in repr(summaries)


def test_dead_registry_entries_are_pruned_while_listing() -> None:
    registry = FakeRegistry(entries={Pid(10): entry(10), Pid(20): entry(20), Pid(999): entry(999)})
    deps = SendDeps(
        sessions=FakeSessions((session(10),)),
        registry=registry,
        poster=FakePoster(),
        probe=FakeProbe(alive={Pid(20)}),
    )
    list_sessions(deps)
    assert registry.deleted == [Pid(999)]
