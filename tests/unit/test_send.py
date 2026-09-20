"""The send use case posts a verbatim message into one named live session."""

from dataclasses import replace

from explain_selection.domain import Pid, SessionKind
from explain_selection.services import (
    NoSuchSession,
    SendDeps,
    Sent,
    Unavailable,
    send_message,
)
from tests.builders import entry, session
from tests.fakes import FakePoster, FakeProbe, FakeRegistry, FakeSessions


def _deps() -> SendDeps:
    return SendDeps(
        sessions=FakeSessions((session(10), session(20))),
        registry=FakeRegistry(entries={Pid(10): entry(10)}),
        poster=FakePoster(),
        probe=FakeProbe(),
    )


def test_a_registered_session_receives_the_text_verbatim_with_its_token() -> None:
    poster = FakePoster()
    result = send_message(Pid(10), "hello {there}\n", replace(_deps(), poster=poster))
    assert isinstance(result, Sent)
    assert result.chars == len("hello {there}\n")
    assert result.target.session.pid == Pid(10)
    (address, content), *rest = poster.posts
    assert rest == []
    assert content == "hello {there}\n"
    assert address.pid == Pid(10)
    assert address.socket_path == entry(10).socket
    assert address.token == entry(10).token


def test_an_unregistered_live_session_is_posted_to_as_an_unverified_peer() -> None:
    poster = FakePoster()
    result = send_message(Pid(20), "x", replace(_deps(), poster=poster))
    assert isinstance(result, Sent)
    assert result.target.session.pid == Pid(20)
    assert result.target.entry is None
    (address, _content) = poster.posts[0]
    assert address.socket_path is None
    assert address.token is None


def test_an_unknown_pid_is_no_such_session_and_nothing_is_posted() -> None:
    poster = FakePoster()
    result = send_message(Pid(999), "x", replace(_deps(), poster=poster))
    assert result == NoSuchSession(Pid(999))
    assert poster.posts == []


def test_a_background_session_is_not_a_valid_target() -> None:
    deps = replace(_deps(), sessions=FakeSessions((session(30, kind=SessionKind.BACKGROUND),)))
    assert send_message(Pid(30), "x", deps) == NoSuchSession(Pid(30))


def test_a_dead_socket_becomes_unavailable_with_the_reason() -> None:
    result = send_message(Pid(10), "x", replace(_deps(), poster=FakePoster(fail=True)))
    assert result == Unavailable(Pid(10), "no socket for pid 10")


def test_registry_entries_for_dead_pids_are_pruned_but_alive_ones_kept() -> None:
    registry = FakeRegistry(entries={Pid(10): entry(10), Pid(20): entry(20), Pid(999): entry(999)})
    deps = replace(
        _deps(),
        sessions=FakeSessions((session(10),)),
        registry=registry,
        probe=FakeProbe(alive={Pid(20)}),
    )
    send_message(Pid(10), "x", deps)
    assert registry.deleted == [Pid(999)]
