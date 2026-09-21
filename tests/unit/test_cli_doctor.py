"""The ``doctor`` subcommand, driven through ``run`` with in-memory fakes."""

import io
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from explain_selection.domain import Check, SessionStatus
from explain_selection.entrypoints.cli import CliDeps, run
from explain_selection.entrypoints.cli_doctor import (
    MANIFEST_RELATIVE,
    build_doctor_deps,
    claude_settings_paths,
    plugin_version_from,
    report_lines,
)
from explain_selection.entrypoints.cli_install import InstallContext
from explain_selection.services import (
    ClaudeSettingsFacts,
    DoctorDeps,
    SendDeps,
    shim_content,
)
from tests.builders import PRIVATE_DIR, PRIVATE_SOCKET, SHIM, entry, file_facts, session
from tests.fakes import (
    FakeClaudeSettings,
    FakeClock,
    FakeFiles,
    FakeProbe,
    FakeRegistry,
    FakeSessions,
    FakeVersions,
)

PLUGIN_ROOT = Path("/plugins/explain-selection")
TEMPLATE = PLUGIN_ROOT / "templates" / "explain-prompt.txt"
HOME = Path("/users/me/.claude/explain-selection")
PYTHON = HOME / "venv" / "bin" / "python"
SKIPPED = [
    "[skip] services-bundle: macOS only",
    "[skip] shortcut: macOS only",
    "[skip] osascript: macOS only",
]


def _no_stdin() -> str:
    raise AssertionError("stdin must not be read")


def _no_send_deps() -> SendDeps:
    raise AssertionError("the send dependencies must not be built")


def _no_install() -> InstallContext:
    raise AssertionError("the install context must not be built")


def _healthy_files() -> FakeFiles:
    return FakeFiles(
        facts={
            HOME: PRIVATE_DIR,
            PYTHON: SHIM,
            HOME / "capture": SHIM,
            HOME / "config.env": file_facts(),
            TEMPLATE: file_facts(),
        },
        texts={HOME / "capture": shim_content(PLUGIN_ROOT, PYTHON), TEMPLATE: "Explain {text}"},
    )


def _healthy_linux(
    *, files: FakeFiles | None = None, sessions: FakeSessions | None = None
) -> DoctorDeps:
    return DoctorDeps(
        files=files if files is not None else _healthy_files(),
        sessions=sessions if sessions is not None else FakeSessions(),
        registry=FakeRegistry(),
        process=FakeProbe(),
        clock=FakeClock(),
        versions=FakeVersions(version="0.1.0"),
        claude_settings=FakeClaudeSettings(),
        mac=None,
        home=HOME,
        plugin_root=PLUGIN_ROOT,
        root_source="environment",
        plugin_version="0.1.0",
        template_path=TEMPLATE,
    )


def _run(build_doctor: Callable[[], DoctorDeps]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    deps = CliDeps(
        stdin_text=_no_stdin,
        build_send_deps=_no_send_deps,
        build_install=_no_install,
        build_doctor=build_doctor,
    )
    code = run(["doctor"], deps, out, err)
    return code, out.getvalue(), err.getvalue()


def test_a_healthy_linux_box_exits_zero_with_the_mac_checks_skipped() -> None:
    code, out, err = _run(_healthy_linux)
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[:2] == ["[ok] home: mode 0700", "[ok] venv: venv/bin/python present"]
    assert lines[-4:-1] == SKIPPED
    assert lines[-1] == "doctor: 11 ok, 0 warn, 0 fail, 3 skipped"
    assert not any(line.startswith("    fix:") for line in lines)


def test_a_missing_venv_exits_one_and_prints_the_fix_line() -> None:
    files = _healthy_files()
    del files.facts[PYTHON]
    code, out, _ = _run(lambda: _healthy_linux(files=files))
    lines = out.splitlines()
    assert code == 1
    at = lines.index("[fail] venv: venv/bin/python missing")
    assert lines[at + 1] == "    fix: run /explain-selection:install"
    # No python means the version probe is skipped too, so `version` fails as well.
    assert lines[-1] == "doctor: 9 ok, 0 warn, 2 fail, 3 skipped"


def test_a_refuse_policy_exits_one() -> None:
    refusing = FakeClaudeSettings(
        facts=ClaudeSettingsFacts(
            cross_session_inbound="refuse", plugin_enabled=True, unreadable_files=()
        )
    )
    code, out, _ = _run(lambda: replace(_healthy_linux(), claude_settings=refusing))
    assert code == 1
    assert "[fail] inbound-policy: crossSessionInbound is refuse" in out.splitlines()
    assert "    fix: set crossSessionInbound to accept in ~/.claude/settings.json" in out


def test_an_unregistered_interactive_session_warns_but_exits_zero() -> None:
    live = FakeSessions(sessions=(session(4242, status=SessionStatus.BUSY),))
    code, out, _ = _run(lambda: _healthy_linux(sessions=live))
    lines = out.splitlines()
    assert code == 0
    at = lines.index("[warn] session 4242: busy interactive unregistered up 9m")
    assert lines[at + 1].startswith("    fix: restart this session with the plugin enabled;")
    assert lines[-1] == "doctor: 11 ok, 1 warn, 0 fail, 3 skipped"


def test_a_registered_session_with_its_socket_is_ok() -> None:
    registered = entry(7, tmux_pane="%1")
    files = _healthy_files()
    files.facts[Path(registered.socket)] = PRIVATE_SOCKET

    def build() -> DoctorDeps:
        deps = _healthy_linux(files=files, sessions=FakeSessions(sessions=(session(7),)))
        return replace(deps, registry=FakeRegistry(entries={registered.pid: registered}))

    code, out, _ = _run(build)
    assert code == 0
    assert "[ok] session 7: idle interactive registered tmux %1 socket ok up 9m" in out.splitlines()


def test_an_unreadable_manifest_fails_the_version_check_without_crashing() -> None:
    code, out, _ = _run(lambda: replace(_healthy_linux(), plugin_version=""))
    assert code == 1
    assert "[fail] version: plugin.json unreadable" in out.splitlines()


def test_a_failing_dependency_build_is_reported_as_could_not_start() -> None:
    def broken() -> DoctorDeps:
        raise OSError("no settings")

    code, out, err = _run(broken)
    assert (code, out) == (1, "")
    assert err == "explain-selection: could not start: no settings\n"


def test_plugin_version_from_reads_the_manifest_or_yields_the_unreadable_marker(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / MANIFEST_RELATIVE
    assert plugin_version_from(manifest) == ""
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name": "explain-selection", "version": "0.1.0", "x": 1}', encoding="utf-8"
    )
    assert plugin_version_from(manifest) == "0.1.0"
    manifest.write_text('{"name": "explain-selection"}', encoding="utf-8")
    assert plugin_version_from(manifest) == ""
    manifest.write_text("{not json", encoding="utf-8")
    assert plugin_version_from(manifest) == ""


def _installed_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """A home with a shim recording a plugin checkout that has a manifest; no root exported."""
    plugin = tmp_path / "plugin"
    (plugin / MANIFEST_RELATIVE).parent.mkdir(parents=True)
    (plugin / MANIFEST_RELATIVE).write_text(
        '{"name": "explain-selection", "version": "9.9.9"}', encoding="utf-8"
    )
    home = tmp_path / "home"
    home.mkdir()
    (home / "capture").write_text(
        shim_content(plugin, home / "venv" / "bin" / "python"), encoding="utf-8"
    )
    monkeypatch.setenv("EXPLAIN_SELECTION_HOME", str(home))
    monkeypatch.delenv("EXPLAIN_SELECTION_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    return home, plugin


def test_build_doctor_deps_takes_the_plugin_root_from_the_shim_when_none_is_exported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Installed in a venv, the package cannot infer its checkout from __file__; the shim can.
    home, plugin = _installed_runtime(tmp_path, monkeypatch)
    deps = build_doctor_deps("other", tmp_path, tmp_path)
    assert (deps.home, deps.plugin_root, deps.plugin_version) == (home, plugin, "9.9.9")
    assert deps.root_source == "shim"


def test_build_doctor_deps_prefers_the_wrapper_export_over_the_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _installed_runtime(tmp_path, monkeypatch)
    monkeypatch.setenv("EXPLAIN_SELECTION_PLUGIN_ROOT", str(tmp_path / "exported"))
    deps = build_doctor_deps("other", tmp_path, tmp_path)
    assert (deps.plugin_root, deps.root_source) == (tmp_path / "exported", "environment")


def test_build_doctor_deps_falls_back_to_the_checkout_without_an_export_or_a_shim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, _ = _installed_runtime(tmp_path, monkeypatch)
    (home / "capture").unlink()
    assert build_doctor_deps("other", tmp_path, tmp_path).root_source == "checkout"


def test_report_lines_format_and_count_every_status() -> None:
    checks: Sequence[Check] = (
        Check(name="a", status="ok", detail="fine", fix=None),
        Check(name="b", status="warn", detail="meh", fix="do x"),
        Check(name="c", status="fail", detail="bad", fix="do y"),
        Check(name="d", status="skip", detail="macOS only", fix=None),
    )
    assert report_lines(checks) == [
        "[ok] a: fine",
        "[warn] b: meh",
        "    fix: do x",
        "[fail] c: bad",
        "    fix: do y",
        "[skip] d: macOS only",
        "doctor: 1 ok, 1 warn, 1 fail, 1 skipped",
    ]


def test_claude_settings_paths_are_user_then_project_then_local() -> None:
    assert claude_settings_paths(Path("/u"), Path("/w")) == (
        Path("/u/.claude/settings.json"),
        Path("/w/.claude/settings.json"),
        Path("/w/.claude/settings.local.json"),
    )
