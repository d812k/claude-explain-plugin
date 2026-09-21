"""MacServicesProbe: bundle from stat, shortcut status from defaults, osascript from which."""

from collections.abc import Sequence
from pathlib import Path

from explain_selection.adapters import CommandResult, MacServicesProbe
from explain_selection.errors import SubprocessError
from tests.fakes import FakeRunner

STATUS = '{ "(null) - Explain selection - runWorkflowAsService" = { "key_equivalent" = "@~e"; }; }'


class _MissingBinaryRunner:
    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        raise SubprocessError(f"{args[0]} not found")


def _no_binary(name: str) -> str | None:
    return None


def _osascript_only(name: str) -> str | None:
    return "/usr/bin/osascript" if name == "osascript" else None


def test_the_bundle_is_looked_up_under_the_services_directory(tmp_path: Path) -> None:
    probe = MacServicesProbe(FakeRunner(), tmp_path, which=_no_binary)
    assert not probe.bundle().exists
    (tmp_path / "Explain selection.workflow").mkdir()
    assert probe.bundle().is_dir


def test_the_shortcut_status_is_the_defaults_output(tmp_path: Path) -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=0, stdout=STATUS, stderr="")])
    assert MacServicesProbe(runner, tmp_path, which=_no_binary).shortcut_status() == STATUS
    assert runner.calls == [("defaults", "read", "pbs", "NSServicesStatus")]


def test_a_failing_or_missing_defaults_command_reads_as_no_status(tmp_path: Path) -> None:
    failing = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr="no domain")])
    assert MacServicesProbe(failing, tmp_path, which=_no_binary).shortcut_status() is None
    missing = MacServicesProbe(_MissingBinaryRunner(), tmp_path, which=_no_binary)
    assert missing.shortcut_status() is None


def test_osascript_is_found_through_the_injected_lookup(tmp_path: Path) -> None:
    assert MacServicesProbe(FakeRunner(), tmp_path, which=_osascript_only).osascript_found()
    assert not MacServicesProbe(FakeRunner(), tmp_path, which=_no_binary).osascript_found()
