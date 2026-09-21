"""The install use case: lay out the runtime home; on macOS register the Services entry."""

import shlex
from pathlib import Path

from explain_selection import domain
from explain_selection.domain import MACOS_ONLY, SHORTCUT_SETTINGS_PATH
from explain_selection.entrypoints.settings import ENV_PREFIX, Settings
from explain_selection.services import (
    MANUAL_SHORTCUT_HINT,
    SERVICE_NAME,
    InstallDeps,
    InstallPlan,
    InstallReport,
    Platform,
    StepResult,
    install_plugin,
    platform_from,
    shim_content,
)
from tests.fakes import FakeInstallFiles, FakeRegistrar

HOME = Path("/Users/me/.claude/explain-selection")
ROOT = Path("/Users/me/plugins/explain-selection")
PYTHON = HOME / "venv" / "bin" / "python"
SERVICES = Path("/Users/me/Library/Services")
CONFIG = HOME / "config.env"
PROMPT = HOME / "explain-prompt.txt"
SHIM = HOME / "capture"
BUNDLE = "Explain selection.workflow"
STEP_NAMES = ("home", "config", "prompt", "shim", "service", "shortcut")


def _plan(
    *, platform: Platform = "darwin", dry_run: bool = False, shortcut: str = "@~e"
) -> InstallPlan:
    return InstallPlan(
        home=HOME,
        plugin_root=ROOT,
        venv_python=PYTHON,
        shortcut=shortcut,
        platform=platform,
        dry_run=dry_run,
    )


def _deps(
    files: FakeInstallFiles | None = None, registrar: FakeRegistrar | None = None
) -> InstallDeps:
    return InstallDeps(
        files=files if files is not None else FakeInstallFiles(),
        registrar=registrar if registrar is not None else FakeRegistrar(status=SERVICE_NAME),
        services_dir=SERVICES,
    )


def _statuses(report: InstallReport) -> dict[str, str]:
    return {step.name: step.status for step in report.steps}


def _details(report: InstallReport) -> dict[str, str]:
    return {step.name: step.detail for step in report.steps}


def test_a_fresh_darwin_install_performs_every_step_in_order() -> None:
    files, registrar = FakeInstallFiles(), FakeRegistrar(status=f"{{ ... {SERVICE_NAME} ... }}")
    report = install_plugin(_plan(), _deps(files, registrar))
    assert tuple(step.name for step in report.steps) == STEP_NAMES
    assert _statuses(report) == dict.fromkeys(STEP_NAMES, "done")
    assert report.ok
    assert files.dirs == [HOME]
    assert set(files.written) == {CONFIG, SHIM}
    assert files.copied == [(ROOT / "templates" / "explain-prompt.txt", PROMPT)]
    assert files.replaced == [(ROOT / "assets" / BUNDLE, SERVICES / BUNDLE)]
    assert registrar.shortcuts == [(SERVICE_NAME, "@~e")]
    assert registrar.refreshes == 1


def test_config_env_names_every_setting_and_points_the_template_at_home() -> None:
    files = FakeInstallFiles()
    install_plugin(_plan(), _deps(files))
    content, mode = files.written[CONFIG]
    assert mode == 0o600
    for name in Settings.model_fields:
        assert f"{ENV_PREFIX}{name.upper()}" in content
    active = [line for line in content.splitlines() if line and not line.startswith("#")]
    assert active == [f"EXPLAIN_SELECTION_PROMPT_TEMPLATE={PROMPT}"]


def test_the_shim_execs_the_venv_python_with_the_plugin_root_exported() -> None:
    files = FakeInstallFiles()
    install_plugin(_plan(), _deps(files))
    content, mode = files.written[SHIM]
    assert mode == 0o700
    assert content == shim_content(ROOT, PYTHON)
    assert content.splitlines() == [
        "#!/bin/sh",
        f"EXPLAIN_SELECTION_PLUGIN_ROOT={ROOT}",
        "export EXPLAIN_SELECTION_PLUGIN_ROOT",
        f'exec {PYTHON} -m explain_selection.entrypoints.capture "$@"',
    ]


def test_the_shim_quotes_paths_with_spaces_and_dollar_signs_for_the_shell() -> None:
    root = Path("/Users/me/My Plugins/$HOME/explain-selection")
    python = Path("/Users/me/My Home/venv/bin/python")
    lines = shim_content(root, python).splitlines()
    assert (
        lines[1] == "EXPLAIN_SELECTION_PLUGIN_ROOT='/Users/me/My Plugins/$HOME/explain-selection'"
    )
    assert lines[3] == (
        "exec '/Users/me/My Home/venv/bin/python' -m explain_selection.entrypoints.capture \"$@\""
    )
    # The shell sees the path as one word, unexpanded.
    assert shlex.split(lines[1]) == [
        "EXPLAIN_SELECTION_PLUGIN_ROOT=/Users/me/My Plugins/$HOME/explain-selection"
    ]
    assert shlex.split(lines[3])[1] == str(python)


def test_existing_config_and_prompt_are_kept_but_the_shim_is_rewritten() -> None:
    files = FakeInstallFiles(existing={CONFIG, PROMPT, SHIM})
    report = install_plugin(_plan(), _deps(files))
    statuses = _statuses(report)
    assert (statuses["config"], statuses["prompt"], statuses["shim"]) == (
        "skipped",
        "skipped",
        "done",
    )
    assert set(files.written) == {SHIM}
    assert files.copied == []
    assert report.ok


def test_other_platforms_skip_the_macos_steps() -> None:
    files, registrar = FakeInstallFiles(), FakeRegistrar()
    report = install_plugin(_plan(platform="other"), _deps(files, registrar))
    statuses, details = _statuses(report), _details(report)
    assert (statuses["service"], statuses["shortcut"]) == ("skipped", "skipped")
    assert (details["service"], details["shortcut"]) == ("macOS only", "macOS only")
    assert (statuses["home"], statuses["shim"]) == ("done", "done")
    assert files.replaced == []
    assert (registrar.shortcuts, registrar.refreshes) == ([], 0)
    assert report.ok


def test_the_installer_reuses_the_doctor_wording_from_the_domain() -> None:
    assert SERVICE_NAME is domain.SERVICE_NAME
    hint = f"set it manually: {SHORTCUT_SETTINGS_PATH}"
    assert hint == MANUAL_SHORTCUT_HINT
    details = _details(install_plugin(_plan(platform="other"), _deps()))
    assert (details["service"], details["shortcut"]) == (MACOS_ONLY, MACOS_ONLY)


def test_a_status_without_the_service_fails_the_shortcut_step() -> None:
    report = install_plugin(_plan(), _deps(registrar=FakeRegistrar(status="{ other = 1; }")))
    assert _statuses(report)["shortcut"] == "failed"
    assert _details(report)["shortcut"] == MANUAL_SHORTCUT_HINT
    assert MANUAL_SHORTCUT_HINT.startswith("set it manually: System Settings > Keyboard")
    assert not report.ok


def test_a_registrar_error_fails_the_shortcut_step_with_the_error_and_the_hint() -> None:
    report = install_plugin(_plan(), _deps(registrar=FakeRegistrar(fail=True)))
    detail = _details(report)["shortcut"]
    assert _statuses(report)["shortcut"] == "failed"
    assert detail.startswith("defaults write failed")
    assert detail.endswith(MANUAL_SHORTCUT_HINT)


def test_dry_run_plans_every_step_and_touches_nothing() -> None:
    files, registrar = FakeInstallFiles(), FakeRegistrar()
    report = install_plugin(_plan(dry_run=True, shortcut="@^x"), _deps(files, registrar))
    assert _statuses(report) == dict.fromkeys(STEP_NAMES, "planned")
    assert all(detail.startswith("would ") for detail in _details(report).values())
    assert "@^x" in _details(report)["shortcut"]
    assert not files.touched
    assert (registrar.shortcuts, registrar.refreshes) == ([], 0)
    assert report.ok


def test_dry_run_reports_existing_files_as_kept() -> None:
    files = FakeInstallFiles(existing={CONFIG})
    report = install_plugin(_plan(dry_run=True), _deps(files))
    details = _details(report)
    assert details["config"] == f"would keep existing {CONFIG}"
    assert details["prompt"] == f"would write {PROMPT}"
    assert not files.touched


def test_a_failing_step_is_recorded_and_later_steps_still_run() -> None:
    files = FakeInstallFiles(fail_paths={SHIM})
    report = install_plugin(_plan(), _deps(files))
    statuses = _statuses(report)
    assert statuses["shim"] == "failed"
    assert _details(report)["shim"] == f"permission denied: {SHIM}"
    assert (statuses["service"], statuses["shortcut"]) == ("done", "done")
    assert not report.ok


def test_platform_from_distinguishes_darwin_from_everything_else() -> None:
    assert platform_from("darwin") == "darwin"
    assert platform_from("linux") == "other"
    assert platform_from("win32") == "other"


def test_a_report_is_ok_unless_a_step_failed() -> None:
    done = StepResult(name="home", status="done", detail="")
    assert InstallReport(steps=(done, StepResult(name="x", status="skipped", detail=""))).ok
    assert InstallReport(steps=()).ok
    assert not InstallReport(steps=(done, StepResult(name="x", status="failed", detail=""))).ok
