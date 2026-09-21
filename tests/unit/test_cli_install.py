"""The ``install`` subcommand, driven through ``run`` with in-memory fakes."""

import io
from collections.abc import Callable, Sequence
from pathlib import Path

from explain_selection.entrypoints.cli import CliDeps, run
from explain_selection.entrypoints.cli_install import InstallContext, describe_shortcut
from explain_selection.services import (
    MANUAL_SHORTCUT_HINT,
    SERVICE_NAME,
    InstallDeps,
    Platform,
    SendDeps,
    shim_content,
)
from tests.fakes import FakeInstallFiles, FakeRegistrar

BUNDLE = "Explain selection.workflow"
STEP_NAMES = ("home", "config", "prompt", "shim", "service", "shortcut")


def _no_stdin() -> str:
    raise AssertionError("stdin must not be read")


def _no_deps() -> SendDeps:
    raise AssertionError("the send dependencies must not be built")


def _context(
    tmp_path: Path,
    *,
    platform: Platform = "darwin",
    files: FakeInstallFiles | None = None,
    registrar: FakeRegistrar | None = None,
) -> InstallContext:
    home = tmp_path / "home"
    return InstallContext(
        home=home,
        plugin_root=tmp_path / "plugin",
        venv_python=home / "venv" / "bin" / "python",
        platform=platform,
        deps=InstallDeps(
            files=files if files is not None else FakeInstallFiles(),
            registrar=registrar if registrar is not None else FakeRegistrar(status=SERVICE_NAME),
            services_dir=tmp_path / "Library" / "Services",
        ),
    )


def _run(argv: Sequence[str], context: InstallContext) -> tuple[int, str, str]:
    return _run_with(argv, lambda: context)


def _run_with(
    argv: Sequence[str], build_install: Callable[[], InstallContext]
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    deps = CliDeps(stdin_text=_no_stdin, build_send_deps=_no_deps, build_install=build_install)
    code = run(argv, deps, out, err)
    return code, out.getvalue(), err.getvalue()


def _step_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("[")]


def test_on_other_platforms_the_macos_steps_are_skipped_and_the_exit_is_zero(
    tmp_path: Path,
) -> None:
    code, out, err = _run(["install"], _context(tmp_path, platform="other"))
    lines = _step_lines(out)
    assert (code, err) == (0, "")
    assert [line.split("]")[0] for line in lines] == ["[done"] * 4 + ["[skipped"] * 2
    assert lines[4:] == ["[skipped] service: macOS only", "[skipped] shortcut: macOS only"]
    assert "Next steps:" in out


def test_on_darwin_every_step_runs_in_order_and_the_next_steps_name_the_shortcut(
    tmp_path: Path,
) -> None:
    files, registrar = FakeInstallFiles(), FakeRegistrar(status=f"{{ {SERVICE_NAME} = 1; }}")
    context = _context(tmp_path, files=files, registrar=registrar)
    code, out, err = _run(["install"], context)
    lines = _step_lines(out)
    assert (code, err) == (0, "")
    assert [line.split(":")[0] for line in lines] == [f"[done] {name}" for name in STEP_NAMES]
    assert files.replaced == [
        (context.plugin_root / "assets" / BUNDLE, context.deps.services_dir / BUNDLE)
    ]
    assert registrar.shortcuts == [(SERVICE_NAME, "@~e")]
    assert registrar.refreshes == 1
    assert out.splitlines()[-7:] == [
        "",
        "Next steps:",
        "  1. Relaunch your terminal apps so the shortcut registers.",
        "  2. Select text and press Command-Option-E (@~e).",
        "  3. The first time several Claude Code sessions are open, macOS asks to allow",
        "     controlling iTerm2 or Terminal; click Allow.",
        "  4. Run `explain-selection doctor` to check everything.",
    ]


def test_the_shortcut_option_is_passed_to_the_registrar(tmp_path: Path) -> None:
    registrar = FakeRegistrar(status=SERVICE_NAME)
    code, out, _ = _run(["install", "--shortcut", "@^x"], _context(tmp_path, registrar=registrar))
    assert code == 0
    assert registrar.shortcuts == [(SERVICE_NAME, "@^x")]
    assert "press Command-Control-X (@^x)." in out


def test_an_unverified_shortcut_is_reported_as_failed_and_exits_one(tmp_path: Path) -> None:
    code, out, err = _run(["install"], _context(tmp_path, registrar=FakeRegistrar(status="")))
    assert (code, err) == (1, "")
    assert f"[failed] shortcut: {MANUAL_SHORTCUT_HINT}" in _step_lines(out)
    assert "Next steps:" in out


def test_dry_run_plans_every_step_touches_nothing_and_exits_zero(tmp_path: Path) -> None:
    files, registrar = FakeInstallFiles(), FakeRegistrar()
    code, out, err = _run(
        ["install", "--dry-run"], _context(tmp_path, files=files, registrar=registrar)
    )
    assert (code, err) == (0, "")
    assert all(line.startswith("[planned] ") for line in _step_lines(out))
    assert len(_step_lines(out)) == len(STEP_NAMES)
    assert not files.touched
    assert (registrar.shortcuts, registrar.refreshes) == ([], 0)


def test_existing_config_and_template_are_not_overwritten(tmp_path: Path) -> None:
    home = tmp_path / "home"
    files = FakeInstallFiles(existing={home / "config.env", home / "explain-prompt.txt"})
    code, out, _ = _run(["install"], _context(tmp_path, files=files))
    assert code == 0
    assert f"[skipped] config: {home / 'config.env'} exists; kept" in _step_lines(out)
    assert f"[skipped] prompt: {home / 'explain-prompt.txt'} exists; kept" in _step_lines(out)
    assert set(files.written) == {home / "capture"}
    assert files.copied == []


def test_the_shim_is_written_executable_with_the_venv_python_and_plugin_root(
    tmp_path: Path,
) -> None:
    files = FakeInstallFiles()
    context = _context(tmp_path, files=files)
    _run(["install"], context)
    content, mode = files.written[context.home / "capture"]
    assert mode == 0o700
    assert content == shim_content(context.plugin_root, context.venv_python)
    assert content.splitlines() == [
        "#!/bin/sh",
        f'EXPLAIN_SELECTION_PLUGIN_ROOT="{context.plugin_root}"',
        "export EXPLAIN_SELECTION_PLUGIN_ROOT",
        f'exec "{context.venv_python}" -m explain_selection.entrypoints.capture "$@"',
    ]


def test_plugin_root_option_overrides_the_context(tmp_path: Path) -> None:
    files = FakeInstallFiles()
    context = _context(tmp_path, files=files)
    other = tmp_path / "elsewhere"
    code, _, _ = _run(["install", "--plugin-root", str(other)], context)
    assert code == 0
    assert files.copied == [
        (other / "templates" / "explain-prompt.txt", context.home / "explain-prompt.txt")
    ]
    assert files.written[context.home / "capture"][0] == shim_content(other, context.venv_python)


def test_a_failing_context_build_is_reported_and_exits_one() -> None:
    def build_install() -> InstallContext:
        raise RuntimeError("config.env is malformed")

    code, out, err = _run_with(["install"], build_install)
    assert (code, out) == (1, "")
    assert err == "explain-selection: could not start: config.env is malformed\n"


def test_describe_shortcut_spells_out_the_modifiers() -> None:
    assert describe_shortcut("@~e") == "Command-Option-E"
    assert describe_shortcut("@$^k") == "Command-Shift-Control-K"
    assert describe_shortcut("e") == "E"
    assert describe_shortcut("@") == "@"
