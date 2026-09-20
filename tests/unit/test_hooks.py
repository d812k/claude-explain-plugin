"""The hook entrypoints turn stdin JSON plus environment into registry writes, quietly."""

import logging
from pathlib import Path

import pytest

from explain_selection.domain import Pid
from explain_selection.entrypoints import register, unregister
from explain_selection.entrypoints.hooks import build_hook_context
from explain_selection.entrypoints.runtime import configure_logging, entrypoint_logger
from explain_selection.services import RegisterDeps
from tests.builders import FAKE_TOKEN, entry
from tests.fakes import FakeClock, FakeRegistry, FakeTtyLookup

SOCKET = "/run/user/501/cc-socks/4242.sock"
STDIN = '{"session_id": "abc", "cwd": "/work/repo", "hook_event_name": "SessionStart"}'
ENVIRON = {
    "CLAUDE_CODE_MESSAGING_SOCKET": SOCKET,
    "CLAUDE_CODE_MESSAGING_TOKEN": str(FAKE_TOKEN),
    "CLAUDE_SESSION_NAME": "reviewer",
    "TMUX": "/tmp/tmux-501/default,1234,0",
    "TMUX_PANE": "%3",
}


def _deps(registry: FakeRegistry) -> RegisterDeps:
    return RegisterDeps(
        clock=FakeClock(), registry=registry, tty_lookup=FakeTtyLookup({Pid(4242): "ttys004"})
    )


def test_context_combines_stdin_with_the_environment() -> None:
    ctx = build_hook_context(STDIN, ENVIRON)
    assert ctx.session_id == "abc"
    assert ctx.cwd == "/work/repo"
    assert ctx.name == "reviewer"
    assert ctx.socket_path == SOCKET
    assert ctx.token == FAKE_TOKEN
    assert ctx.tmux == "/tmp/tmux-501/default,1234,0"
    assert ctx.tmux_pane == "%3"


def test_empty_environment_values_become_none() -> None:
    ctx = build_hook_context("", {"CLAUDE_SESSION_NAME": "", "TMUX_PANE": ""})
    assert ctx == build_hook_context("", {})
    assert ctx.name is None
    assert ctx.socket_path is None


def test_register_writes_the_entry_and_exits_zero() -> None:
    registry = FakeRegistry()
    assert register.run(STDIN, ENVIRON, _deps(registry)) == 0
    saved = registry.entries[Pid(4242)]
    assert saved.session_id == "abc"
    assert saved.cwd == "/work/repo"
    assert saved.tty == "ttys004"
    assert saved.name == "reviewer"
    assert saved.tmux_pane == "%3"
    assert saved.registered_at_ms == FakeClock().now


def test_register_without_a_socket_writes_nothing_and_still_exits_zero() -> None:
    registry = FakeRegistry()
    assert register.run(STDIN, {}, _deps(registry)) == 0
    assert registry.entries == {}


def test_register_tolerates_malformed_stdin() -> None:
    registry = FakeRegistry()
    assert register.run("not json", ENVIRON, _deps(registry)) == 0
    assert registry.entries[Pid(4242)].cwd == ""


def test_unregister_deletes_the_entry_for_the_socket_pid() -> None:
    registry = FakeRegistry(entries={Pid(4242): entry(4242), Pid(7): entry(7)})
    assert unregister.run(STDIN, ENVIRON, _deps(registry)) == 0
    assert registry.deleted == [Pid(4242)]
    assert Pid(7) in registry.entries


def test_unregister_without_a_socket_deletes_nothing() -> None:
    registry = FakeRegistry(entries={Pid(4242): entry(4242)})
    assert unregister.run(STDIN, {}, _deps(registry)) == 0
    assert registry.deleted == []


def test_logs_describe_the_outcome_without_the_token(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="explain_selection"):
        register.run(STDIN, ENVIRON, _deps(FakeRegistry()))
        register.run(STDIN, {}, _deps(FakeRegistry()))
    assert "register: registered pid 4242 cwd=/work/repo tty=ttys004 pane=%3" in caplog.text
    assert "register: skipped: no messaging socket in environment" in caplog.text
    assert str(FAKE_TOKEN) not in caplog.text


def test_main_uses_the_root_logger_so_dunder_main_records_reach_the_file(
    tmp_path: Path,
) -> None:
    log_file = tmp_path / "explain-selection.log"
    target = entrypoint_logger()
    handlers_before, level_before = list(target.handlers), target.level
    try:
        configure_logging(log_file, target)
        logging.getLogger("__main__").info("from a module run with python -m")
    finally:
        for handler in target.handlers:
            if handler not in handlers_before:
                handler.close()
                target.removeHandler(handler)
        target.setLevel(level_before)
    assert "from a module run with python -m" in log_file.read_text()


def test_configure_logging_writes_a_private_file(tmp_path: Path) -> None:
    log_file = tmp_path / "home" / "explain-selection.log"
    target = logging.Logger("test-hooks-configure")
    configure_logging(log_file, target)
    target.info("hello from the hook")
    for handler in target.handlers:
        handler.close()
    assert "hello from the hook" in log_file.read_text()
    assert log_file.stat().st_mode & 0o777 == 0o600
    assert log_file.parent.stat().st_mode & 0o777 == 0o700
