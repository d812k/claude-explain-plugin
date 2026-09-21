"""The doctor use case: facts from the adapters, verdicts from the domain, nothing written."""

from dataclasses import replace
from pathlib import Path

from explain_selection.domain import (
    MacFacts,
    Pid,
    SessionKind,
    SessionStatus,
    evaluate,
)
from explain_selection.services import (
    ClaudeSettingsFacts,
    DoctorDeps,
    gather_facts,
    installed_plugin_root,
    run_doctor,
    shim_content,
)
from tests.builders import PRIVATE_DIR, PRIVATE_SOCKET, SHIM, entry, file_facts, session
from tests.fakes import (
    FakeClaudeSettings,
    FakeClock,
    FakeFiles,
    FakeMac,
    FakeProbe,
    FakeRegistry,
    FakeSessions,
    FakeVersions,
)

PLUGIN_ROOT = Path("/plugins/explain-selection")
TEMPLATE = PLUGIN_ROOT / "templates" / "explain-prompt.txt"
HOME = Path("/users/me/.claude/explain-selection")
PYTHON = HOME / "venv" / "bin" / "python"
SHIM_PATH = HOME / "capture"
NOW = 1_700_000_600_000


def _healthy_files() -> FakeFiles:
    return FakeFiles(
        facts={HOME: PRIVATE_DIR, PYTHON: SHIM, SHIM_PATH: SHIM, HOME / "config.env": file_facts()},
        texts={SHIM_PATH: shim_content(PLUGIN_ROOT, PYTHON), TEMPLATE: "Explain:\n{text}\n"},
    )


def _deps(
    *,
    files: FakeFiles | None = None,
    sessions: FakeSessions | None = None,
    registry: FakeRegistry | None = None,
    probe: FakeProbe | None = None,
    mac: FakeMac | None = None,
) -> DoctorDeps:
    """Healthy dependencies; swap ``versions`` or ``claude_settings`` with ``replace``."""
    return DoctorDeps(
        files=files if files is not None else _healthy_files(),
        sessions=sessions if sessions is not None else FakeSessions(),
        registry=registry if registry is not None else FakeRegistry(),
        process=probe if probe is not None else FakeProbe(),
        clock=FakeClock(now=NOW),
        versions=FakeVersions(),
        claude_settings=FakeClaudeSettings(),
        mac=mac,
        home=HOME,
        plugin_root=PLUGIN_ROOT,
        plugin_version="0.1.0",
        template_path=TEMPLATE,
    )


def test_a_healthy_home_yields_healthy_runtime_facts() -> None:
    versions = FakeVersions(version="0.1.0")
    runtime = gather_facts(replace(_deps(), versions=versions)).runtime
    assert runtime.home == PRIVATE_DIR
    assert runtime.venv_python == SHIM
    assert (runtime.installed_version, runtime.plugin_version) == ("0.1.0", "0.1.0")
    assert runtime.shim == SHIM
    assert (runtime.shim_plugin_root, runtime.plugin_root) == (str(PLUGIN_ROOT), str(PLUGIN_ROOT))
    assert runtime.config_present
    assert (runtime.template_present, runtime.template_has_placeholder) == (True, True)
    assert versions.asked == [PYTHON]


def test_an_empty_home_yields_missing_facts_and_never_probes_the_version() -> None:
    versions = FakeVersions()
    runtime = gather_facts(replace(_deps(files=FakeFiles()), versions=versions)).runtime
    assert not runtime.home.exists
    assert not runtime.venv_python.exists
    assert runtime.installed_version is None
    assert versions.asked == []
    assert runtime.shim_plugin_root is None
    assert not runtime.config_present
    assert (runtime.template_present, runtime.template_has_placeholder) == (False, False)


def test_the_shim_plugin_root_is_parsed_from_the_shim_and_the_template_is_inspected() -> None:
    files = _healthy_files()
    files.texts[SHIM_PATH] = shim_content(Path("/moved"), PYTHON)
    files.texts[TEMPLATE] = "no placeholder here"
    runtime = gather_facts(_deps(files=files)).runtime
    assert runtime.shim_plugin_root == "/moved"
    assert (runtime.template_present, runtime.template_has_placeholder) == (True, False)
    files.texts[SHIM_PATH] = "#!/bin/sh\nexec something\n"
    assert gather_facts(_deps(files=files)).runtime.shim_plugin_root is None


def test_installed_plugin_root_is_the_shim_record_else_the_fallback() -> None:
    fallback = Path("/site-packages/guess")
    files = _healthy_files()
    assert installed_plugin_root(files, HOME, fallback) == PLUGIN_ROOT
    files.texts[SHIM_PATH] = "#!/bin/sh\nexec something\n"
    assert installed_plugin_root(files, HOME, fallback) == fallback
    del files.texts[SHIM_PATH]
    assert installed_plugin_root(files, HOME, fallback) == fallback


def test_live_sessions_become_session_facts_with_the_registered_socket_inspected() -> None:
    live = FakeSessions(
        sessions=(
            session(11, status=SessionStatus.BUSY),
            session(12, kind=SessionKind.BACKGROUND),
        )
    )
    registered = entry(11, tmux_pane="%3", socket="/run/user/501/cc-socks/11.sock")
    files = _healthy_files()
    files.facts[Path(registered.socket)] = PRIVATE_SOCKET
    registry = FakeRegistry(entries={registered.pid: registered})
    claude = gather_facts(_deps(files=files, sessions=live, registry=registry)).claude
    assert claude.agents_error is None
    assert [s.pid for s in claude.sessions] == [Pid(11), Pid(12)]
    first, second = claude.sessions
    assert (first.status, first.kind, first.registered) == (
        SessionStatus.BUSY,
        SessionKind.INTERACTIVE,
        True,
    )
    assert (first.tmux, first.socket) == ("%3", PRIVATE_SOCKET)
    assert first.age_ms == NOW - session(11).started_at_ms
    assert (second.kind, second.registered, second.tmux, second.socket) == (
        SessionKind.BACKGROUND,
        False,
        None,
        None,
    )
    assert Path(registered.socket) in files.inspected


def test_stale_entries_are_counted_but_never_deleted() -> None:
    live = FakeSessions(sessions=(session(11),))
    registry = FakeRegistry(entries={e.pid: e for e in (entry(11), entry(12), entry(13))})
    probe = FakeProbe(alive={Pid(12)})
    claude = gather_facts(_deps(sessions=live, registry=registry, probe=probe)).claude
    assert claude.stale_entries == 1
    assert registry.deleted == []
    assert sorted(probe.asked) == [Pid(12), Pid(13)]
    assert len(registry.entries) == 3


def test_a_failing_agents_query_becomes_the_error_text_and_leaves_the_rest_intact() -> None:
    registry = FakeRegistry(entries={Pid(13): entry(13)})
    deps = _deps(sessions=FakeSessions(fail=True), registry=registry, probe=FakeProbe())
    claude = gather_facts(deps).claude
    assert claude.agents_error == "claude agents failed"
    assert claude.sessions == ()
    assert claude.stale_entries == 1
    assert claude.plugin_enabled


def test_claude_settings_facts_are_passed_through() -> None:
    settings = FakeClaudeSettings(
        facts=ClaudeSettingsFacts(cross_session_inbound="hold", plugin_enabled=False)
    )
    claude = gather_facts(replace(_deps(), claude_settings=settings)).claude
    assert (claude.cross_session_inbound, claude.plugin_enabled) == ("hold", False)


def test_mac_facts_are_absent_off_macos_and_probed_on_it() -> None:
    assert gather_facts(_deps()).mac is None
    mac = FakeMac(bundle_facts=PRIVATE_DIR, status="{ Explain selection = 1; }", osascript=False)
    assert gather_facts(_deps(mac=mac)).mac == MacFacts(
        bundle=PRIVATE_DIR, shortcut_status="{ Explain selection = 1; }", osascript_found=False
    )


def test_run_doctor_evaluates_the_gathered_facts() -> None:
    deps = _deps(sessions=FakeSessions(sessions=(session(11),)))
    checks = run_doctor(deps)
    assert checks == evaluate(gather_facts(deps))
    assert [check.name for check in checks][7:10] == ["agents", "session 11", "stale-entries"]
    assert [check.status for check in checks[:8]] == ["ok"] * 8
