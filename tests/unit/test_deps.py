"""The composition root wires real adapters to the paths in Settings."""

from pathlib import Path

from explain_selection.adapters import (
    CommandResult,
    OsProcessProbe,
    SystemClock,
    TmuxAwareFocus,
)
from explain_selection.domain import Pid, RememberedTarget
from explain_selection.entrypoints.deps import (
    ProcessInfo,
    build_deliver_deps,
    build_register_deps,
)
from explain_selection.entrypoints.settings import Settings
from tests.builders import entry
from tests.fakes import FakeRunner


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        home=tmp_path / "home", prompt_template=tmp_path / "p.txt", fallback_cwd=tmp_path
    )


def test_register_deps_store_entries_under_the_sessions_dir(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    deps = build_register_deps(settings, FakeRunner())
    deps.registry.save(entry(4242))
    assert (settings.sessions_dir / "4242.json").is_file()
    assert isinstance(deps.clock, SystemClock)


def test_register_deps_look_up_ttys_through_ps(tmp_path: Path) -> None:
    runner = FakeRunner()
    build_register_deps(_settings(tmp_path), runner).tty_lookup.tty_for(Pid(7))
    assert runner.calls == [("ps", "-o", "tty=", "-p", "7")]


def test_deliver_deps_use_the_derived_paths(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    deps = build_deliver_deps(settings, {}, ProcessInfo(uid=501), FakeRunner())
    deps.memory.save(RememberedTarget(Pid(9), 1))
    written = Path(deps.tempfiles.write("long selection"))
    assert settings.last_target_file.is_file()
    assert written.parent == settings.temp_dir
    assert isinstance(deps.focus, TmuxAwareFocus)
    assert isinstance(deps.probe, OsProcessProbe)


def test_deliver_deps_list_sessions_through_the_claude_cli(tmp_path: Path) -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=0, stdout="[]", stderr="")])
    deps = build_deliver_deps(_settings(tmp_path), {}, ProcessInfo(uid=501), runner)
    assert deps.sessions.list_interactive() == ()
    assert runner.calls == [("claude", "agents", "--json")]
