"""The register use case writes a version-1 entry keyed by the socket pid."""

from dataclasses import replace

from explain_selection.domain import InboxToken, Pid, SessionId
from explain_selection.services import (
    HookContext,
    RegisterDeps,
    Registered,
    Removed,
    Skipped,
    register_session,
    unregister_session,
)
from tests.fakes import FakeClock, FakeRegistry, FakeTtyLookup

SOCKET = "/run/user/501/cc-socks/2268544.sock"
TOKEN = InboxToken("secret-token")
DEFAULT_CTX = HookContext(
    session_id=SessionId("abc"),
    cwd="/work/proj",
    name="proj",
    socket_path=SOCKET,
    token=TOKEN,
    tmux=None,
    tmux_pane=None,
)


def _deps(registry: FakeRegistry, *, ttys: dict[Pid, str] | None = None) -> RegisterDeps:
    return RegisterDeps(
        clock=FakeClock(now=1_700_000_123_000),
        registry=registry,
        tty_lookup=FakeTtyLookup(ttys=ttys or {}),
    )


def test_registering_writes_an_entry_keyed_by_the_socket_pid() -> None:
    registry = FakeRegistry()
    deps = _deps(registry, ttys={Pid(2268544): "pts/2"})
    result = register_session(DEFAULT_CTX, deps)
    assert isinstance(result, Registered)
    entry = result.entry
    assert entry.pid == 2268544
    assert entry.tty == "pts/2"
    assert entry.cwd == "/work/proj"
    assert entry.socket == SOCKET
    assert entry.token == TOKEN
    assert entry.registered_at_ms == 1_700_000_123_000
    assert entry.version == 1
    assert registry.entries[Pid(2268544)] == entry


def test_tmux_fields_are_carried_through() -> None:
    deps = _deps(FakeRegistry())
    ctx = replace(DEFAULT_CTX, tmux="/tmp/tmux-501/default,1,0", tmux_pane="%7")
    result = register_session(ctx, deps)
    assert isinstance(result, Registered)
    assert result.entry.tmux_pane == "%7"


def test_missing_socket_is_skipped_without_writing() -> None:
    registry = FakeRegistry()
    result = register_session(replace(DEFAULT_CTX, socket_path=None), _deps(registry))
    assert isinstance(result, Skipped)
    assert registry.entries == {}


def test_non_cc_socks_path_is_skipped() -> None:
    registry = FakeRegistry()
    ctx = replace(DEFAULT_CTX, socket_path="/tmp/something/else.txt")
    result = register_session(ctx, _deps(registry))
    assert isinstance(result, Skipped)
    assert registry.entries == {}


def test_missing_token_is_skipped() -> None:
    registry = FakeRegistry()
    result = register_session(replace(DEFAULT_CTX, token=None), _deps(registry))
    assert isinstance(result, Skipped)
    assert registry.entries == {}


def test_absent_tty_is_recorded_as_none() -> None:
    result = register_session(DEFAULT_CTX, _deps(FakeRegistry(), ttys={}))
    assert isinstance(result, Registered)
    assert result.entry.tty is None


def test_unregister_deletes_the_entry_for_the_socket_pid() -> None:
    registry = FakeRegistry()
    deps = _deps(registry)
    register_session(DEFAULT_CTX, deps)
    result = unregister_session(DEFAULT_CTX, deps)
    assert result == Removed(pids=(Pid(2268544),))
    assert registry.deleted == [Pid(2268544)]
    assert registry.entries == {}


def test_unregister_without_socket_and_no_matching_entry_is_skipped() -> None:
    registry = FakeRegistry()
    result = unregister_session(replace(DEFAULT_CTX, socket_path=None), _deps(registry))
    assert isinstance(result, Skipped)
    assert registry.deleted == []


def test_unregister_without_socket_falls_back_to_the_session_id() -> None:
    registry = FakeRegistry()
    deps = _deps(registry)
    register_session(DEFAULT_CTX, deps)
    result = unregister_session(replace(DEFAULT_CTX, socket_path=None, token=None), deps)
    assert result == Removed(pids=(Pid(2268544),))
    assert registry.deleted == [Pid(2268544)]
    assert registry.entries == {}


def test_unregister_by_session_id_leaves_other_sessions_alone() -> None:
    registry = FakeRegistry()
    deps = _deps(registry)
    register_session(DEFAULT_CTX, deps)
    other = replace(
        DEFAULT_CTX,
        session_id=SessionId("other"),
        socket_path="/run/user/501/cc-socks/999.sock",
    )
    register_session(other, deps)
    result = unregister_session(replace(other, socket_path=None, token=None), deps)
    assert result == Removed(pids=(Pid(999),))
    assert registry.deleted == [Pid(999)]
    assert set(registry.entries) == {Pid(2268544)}


def test_unregister_without_socket_or_session_id_is_skipped() -> None:
    registry = FakeRegistry()
    deps = _deps(registry)
    register_session(DEFAULT_CTX, deps)
    result = unregister_session(replace(DEFAULT_CTX, socket_path=None, session_id=None), deps)
    assert isinstance(result, Skipped)
    assert registry.deleted == []
    assert set(registry.entries) == {Pid(2268544)}
