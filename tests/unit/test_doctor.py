"""The doctor's verdicts: one check per rule, each non-ok check with an exact fix."""

from dataclasses import replace

import pytest

from explain_selection.domain import (
    UNREADABLE_PLUGIN_VERSION,
    Check,
    ClaudeFacts,
    DoctorFacts,
    MacFacts,
    RuntimeFacts,
    SessionFacts,
    SessionKind,
    SessionStatus,
    checks_ok,
    evaluate,
)
from tests.builders import (
    HEALTHY_RUNTIME,
    MISSING_FILE,
    PLUGIN_ROOT,
    TEMPLATE_PATH,
    UNREADABLE_FILE,
    claude_facts,
    doctor_facts,
    file_facts,
    mac_facts,
    session_facts,
)

INSTALL_FIX = "run /explain-selection:install"
BOOTSTRAP_FIX = f"run {PLUGIN_ROOT}/scripts/bootstrap.sh"
SETTINGS_PATH = (
    "System Settings > Keyboard > Keyboard Shortcuts > Services > Text > Explain selection"
)
ORDER = (
    "home",
    "venv",
    "version",
    "shim",
    "config",
    "template",
    "plugin-enabled",
    "settings-files",
    "agents",
    "stale-entries",
    "inbound-policy",
    "services-bundle",
    "shortcut",
    "osascript",
)


def _by_name(checks: tuple[Check, ...], name: str) -> Check:
    matches = [check for check in checks if check.name == name]
    assert len(matches) == 1, name
    return matches[0]


def _runtime_check(name: str, runtime: RuntimeFacts) -> Check:
    return _by_name(evaluate(doctor_facts(runtime=runtime)), name)


def _claude_check(name: str, claude: ClaudeFacts) -> Check:
    return _by_name(evaluate(doctor_facts(claude=claude)), name)


def _session_check(session: SessionFacts) -> Check:
    return _claude_check(f"session {session.pid}", claude_facts(sessions=(session,)))


def _mac_check(name: str, mac: MacFacts) -> Check:
    return _by_name(evaluate(doctor_facts(mac=mac)), name)


def test_a_healthy_linux_box_passes_every_check_and_skips_the_mac_ones() -> None:
    checks = evaluate(doctor_facts())
    assert [check.name for check in checks] == list(ORDER)
    assert [check.status for check in checks] == ["ok"] * 11 + ["skip"] * 3
    assert all(check.fix is None for check in checks)
    assert {check.detail for check in checks[11:]} == {"macOS only"}
    assert checks_ok(checks)


def test_a_healthy_mac_passes_every_check() -> None:
    checks = evaluate(doctor_facts(mac=mac_facts()))
    assert [check.status for check in checks] == ["ok"] * 14


def test_a_missing_home_fails_and_a_permissive_home_warns() -> None:
    missing = _runtime_check("home", replace(HEALTHY_RUNTIME, home=MISSING_FILE))
    assert (missing.status, missing.fix) == ("fail", INSTALL_FIX)
    loose = file_facts(mode=0o755, is_dir=True)
    permissive = _runtime_check("home", replace(HEALTHY_RUNTIME, home=loose))
    assert (permissive.status, permissive.fix) == ("warn", INSTALL_FIX)
    assert "0755" in permissive.detail
    not_dir = _runtime_check("home", replace(HEALTHY_RUNTIME, home=file_facts()))
    assert not_dir.status == "fail"


def test_a_missing_venv_python_fails_with_the_install_fix() -> None:
    facts = doctor_facts(runtime=replace(HEALTHY_RUNTIME, venv_python=MISSING_FILE))
    check = _by_name(evaluate(facts), "venv")
    assert (check.status, check.fix) == ("fail", INSTALL_FIX)
    assert not checks_ok(evaluate(facts))


def test_version_fails_when_nothing_is_installed_and_warns_on_a_mismatch() -> None:
    none = _runtime_check("version", replace(HEALTHY_RUNTIME, installed_version=None))
    assert (none.status, none.fix) == ("fail", BOOTSTRAP_FIX)
    old = _runtime_check("version", replace(HEALTHY_RUNTIME, installed_version="0.0.9"))
    assert (old.status, old.fix) == ("warn", BOOTSTRAP_FIX)
    assert "0.0.9" in old.detail
    assert "0.1.0" in old.detail
    same = _by_name(evaluate(doctor_facts()), "version")
    assert (same.status, same.detail) == ("ok", "0.1.0")


def test_version_fails_when_the_manifest_could_not_be_read() -> None:
    runtime = replace(HEALTHY_RUNTIME, plugin_version=UNREADABLE_PLUGIN_VERSION)
    check = _runtime_check("version", runtime)
    assert (check.status, check.detail) == ("fail", "plugin.json unreadable")
    assert check.fix == f"the checkout at {PLUGIN_ROOT} is incomplete; reinstall it with /plugin"
    gone = _runtime_check("version", replace(runtime, root_source="shim"))
    assert (gone.status, gone.detail) == ("fail", "plugin.json unreadable")
    assert gone.fix == (
        f"the recorded plugin root {PLUGIN_ROOT} is gone: reinstall the plugin with /plugin, "
        f"then {INSTALL_FIX}"
    )


def test_a_root_taken_from_the_shim_is_ok_and_says_so_in_the_shim_detail() -> None:
    check = _runtime_check("shim", replace(HEALTHY_RUNTIME, root_source="shim"))
    assert (check.status, check.fix) == ("ok", None)
    assert check.detail == (
        f"capture points at {PLUGIN_ROOT} (root taken from the shim; the plugin export was not set)"
    )
    plain = _by_name(evaluate(doctor_facts()), "shim")
    assert plain.detail == f"capture points at {PLUGIN_ROOT}"


def test_shim_fails_when_missing_or_not_executable_and_warns_when_the_plugin_moved() -> None:
    missing = _runtime_check("shim", replace(HEALTHY_RUNTIME, shim=MISSING_FILE))
    assert (missing.status, missing.fix) == ("fail", INSTALL_FIX)
    plain = _runtime_check("shim", replace(HEALTHY_RUNTIME, shim=file_facts()))
    assert (plain.status, plain.fix) == ("fail", INSTALL_FIX)
    moved = _runtime_check("shim", replace(HEALTHY_RUNTIME, shim_plugin_root="/elsewhere"))
    assert (moved.status, moved.fix) == ("warn", f"the plugin moved: {INSTALL_FIX}")
    assert "/elsewhere" in moved.detail
    unparsed = _runtime_check("shim", replace(HEALTHY_RUNTIME, shim_plugin_root=None))
    assert (unparsed.status, unparsed.fix) == ("fail", INSTALL_FIX)


def test_a_missing_config_only_warns() -> None:
    runtime = replace(HEALTHY_RUNTIME, config_present=False)
    check = _runtime_check("config", runtime)
    assert (check.status, check.fix) == ("warn", f"{INSTALL_FIX} to write config.env")
    assert checks_ok(evaluate(doctor_facts(runtime=runtime)))


@pytest.mark.parametrize(
    ("name", "field", "what", "path"),
    [
        ("home", "home", "home", "<home>"),
        ("venv", "venv_python", "venv/bin/python", "<home>/venv/bin/python"),
        ("shim", "shim", "capture", "<home>/capture"),
        ("template", "template", "prompt template", TEMPLATE_PATH),
    ],
)
def test_a_runtime_file_that_exists_but_cannot_be_read_fails_with_a_permissions_fix(
    name: str, field: str, what: str, path: str
) -> None:
    check = _runtime_check(name, replace(HEALTHY_RUNTIME, **{field: UNREADABLE_FILE}))
    assert (check.status, check.detail) == ("fail", f"{what} exists but cannot be read")
    assert check.fix == f"check ownership and permissions of {path}"


def test_an_unreadable_socket_or_bundle_fails_with_a_permissions_fix() -> None:
    socket = _session_check(session_facts(11, socket=UNREADABLE_FILE))
    assert (socket.status, socket.fix) == (
        "fail",
        "check ownership and permissions of the inbox socket",
    )
    assert "socket unreadable" in socket.detail
    bundle = _mac_check("services-bundle", mac_facts(bundle=UNREADABLE_FILE))
    assert (bundle.status, bundle.detail) == (
        "fail",
        "Explain selection.workflow exists but cannot be read",
    )
    assert bundle.fix == (
        "check ownership and permissions of ~/Library/Services/Explain selection.workflow"
    )


def test_the_template_must_exist_and_contain_the_placeholder() -> None:
    absent = _runtime_check("template", replace(HEALTHY_RUNTIME, template=MISSING_FILE))
    assert (absent.status, absent.fix) == ("fail", INSTALL_FIX)
    assert TEMPLATE_PATH in absent.detail
    no_slot = _runtime_check("template", replace(HEALTHY_RUNTIME, template_has_placeholder=False))
    assert (no_slot.status, no_slot.fix) == (
        "fail",
        f"add {{text}} to {TEMPLATE_PATH}, or delete the file and rerun /explain-selection:install",
    )
    assert "{text}" in no_slot.detail
    assert TEMPLATE_PATH in no_slot.detail
    fine = _by_name(evaluate(doctor_facts()), "template")
    assert fine.status == "ok"
    assert TEMPLATE_PATH in fine.detail


def test_a_disabled_plugin_warns_with_the_plugin_command() -> None:
    check = _claude_check("plugin-enabled", claude_facts(plugin_enabled=False))
    assert (check.status, check.fix) == (
        "warn",
        "enable the plugin with /plugin so the hooks register sessions",
    )


def test_unreadable_settings_files_warn_and_are_named_in_the_fix() -> None:
    files = ("/u/.claude/settings.json", "/w/.claude/settings.local.json")
    broken = replace(claude_facts(), unreadable_settings=files)
    check = _claude_check("settings-files", broken)
    assert (check.status, check.detail) == (
        "warn",
        "skipped /u/.claude/settings.json, /w/.claude/settings.local.json",
    )
    assert check.fix == "fix the JSON in /u/.claude/settings.json, /w/.claude/settings.local.json"
    fine = _claude_check("settings-files", claude_facts())
    assert (fine.status, fine.detail) == ("ok", "all readable")


def test_agents_fails_with_the_adapter_error_and_otherwise_counts_sessions() -> None:
    broken = _claude_check("agents", claude_facts(agents_error="claude not found"))
    assert (broken.status, broken.detail) == ("fail", "claude not found")
    assert broken.fix == "check that claude is on PATH and claude agents --json works"
    two = claude_facts(sessions=(session_facts(11), session_facts(12)))
    assert _claude_check("agents", two).detail == "2 live sessions"
    blank = _claude_check("agents", claude_facts(agents_error=""))
    assert (blank.status, blank.detail) == ("fail", "claude agents --json failed")


def test_each_session_gets_a_check_between_agents_and_stale_entries() -> None:
    in_tmux = replace(session_facts(11, age_ms=125_000), tmux="main")
    facts = claude_facts(sessions=(in_tmux, session_facts(12)))
    names = [check.name for check in evaluate(doctor_facts(claude=facts))]
    assert names[8:12] == ["agents", "session 11", "session 12", "stale-entries"]
    first = _claude_check("session 11", facts)
    assert (first.status, first.fix) == ("ok", None)
    assert first.detail == "idle interactive registered tmux main socket ok up 2m"


def test_an_unregistered_interactive_session_warns_but_a_background_one_does_not() -> None:
    busy = replace(session_facts(11, registered=False, age_ms=60_000), status=SessionStatus.BUSY)
    check = _session_check(busy)
    assert check.status == "warn"
    assert check.detail == "busy interactive unregistered up 1m"
    assert check.fix == (
        "restart this session with the plugin enabled; token-less messages are held by "
        "sessions that bypass permission prompts"
    )
    quiet = _session_check(session_facts(12, registered=False, kind=SessionKind.BACKGROUND))
    assert (quiet.status, quiet.fix) == ("ok", None)


def test_a_registered_session_whose_socket_is_gone_fails() -> None:
    check = _session_check(session_facts(11, socket=MISSING_FILE))
    assert (check.status, check.fix) == ("fail", "the session's inbox socket is gone; restart it")
    assert "socket missing" in check.detail
    not_socket = _session_check(session_facts(12, socket=file_facts(mode=0o600)))
    assert not_socket.status == "fail"


def test_a_socket_open_to_other_users_warns() -> None:
    check = _session_check(session_facts(11, socket=file_facts(mode=0o660, is_socket=True)))
    assert check.status == "warn"
    assert check.fix is not None
    assert check.fix.startswith("socket is accessible to other users")


def test_stale_entries_warn_with_the_prune_hint() -> None:
    check = _claude_check("stale-entries", claude_facts(stale_entries=2))
    assert (check.status, check.detail) == ("warn", "2 entries for dead sessions")
    assert check.fix == "capture prunes them; or delete <home>/sessions/<pid>.json for dead pids"
    assert _by_name(evaluate(doctor_facts()), "stale-entries").status == "ok"


def test_the_inbound_policy_fails_on_refuse_warns_on_hold_and_accepts_the_default() -> None:
    refuse = _claude_check("inbound-policy", claude_facts(cross_session_inbound="refuse"))
    assert (refuse.status, refuse.fix) == (
        "fail",
        "set crossSessionInbound to accept in ~/.claude/settings.json",
    )
    hold = _claude_check("inbound-policy", claude_facts(cross_session_inbound="hold"))
    assert (hold.status, hold.fix) == (
        "warn",
        "set crossSessionInbound to accept, or approve each message",
    )
    accept = _claude_check("inbound-policy", claude_facts(cross_session_inbound="accept"))
    assert (accept.status, accept.detail) == ("ok", "accept")
    unset = _by_name(evaluate(doctor_facts()), "inbound-policy")
    assert (unset.status, unset.detail) == ("ok", "default: token-bearing messages are accepted")


def test_on_macos_the_bundle_the_shortcut_and_osascript_are_checked() -> None:
    no_bundle = _mac_check("services-bundle", mac_facts(bundle=MISSING_FILE))
    assert (no_bundle.status, no_bundle.fix) == ("fail", INSTALL_FIX)
    no_status = _mac_check("shortcut", mac_facts(shortcut_status=None))
    assert (no_status.status, no_status.fix) == ("fail", SETTINGS_PATH)
    other = _mac_check("shortcut", mac_facts(shortcut_status="{ Other = 1; }"))
    assert (other.status, other.fix) == ("fail", SETTINGS_PATH)
    no_osascript = _mac_check("osascript", mac_facts(osascript_found=False))
    assert no_osascript.status == "fail"
    assert no_osascript.fix is not None


def test_checks_ok_tolerates_warnings_and_skips_but_not_failures() -> None:
    assert checks_ok((Check(name="a", status="warn", detail="", fix="x"),))
    assert checks_ok((Check(name="a", status="skip", detail="", fix=None),))
    assert not checks_ok((Check(name="a", status="fail", detail="", fix="x"),))
    assert checks_ok(())


def test_doctor_facts_hold_the_three_parts() -> None:
    facts = DoctorFacts(runtime=HEALTHY_RUNTIME, claude=claude_facts(), mac=None)
    assert facts == doctor_facts()
