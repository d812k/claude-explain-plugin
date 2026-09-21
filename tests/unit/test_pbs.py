"""PbsServicesRegistrar drives `defaults` and `pbs` through the injected runner."""

from collections.abc import Sequence

import pytest

from explain_selection.adapters import PBS, CommandResult, PbsServicesRegistrar
from explain_selection.errors import InstallError, SubprocessError
from tests.fakes import FakeRunner

STATUS_ARGS = ("defaults", "read", "pbs", "NSServicesStatus")


class _MissingBinaryRunner:
    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        raise SubprocessError(f"{args[0]} not found")


def test_set_shortcut_adds_the_workflow_entry_to_the_services_status() -> None:
    runner = FakeRunner()
    PbsServicesRegistrar(runner).set_shortcut("Explain selection", "@~e")
    assert runner.calls == [
        (
            "defaults",
            "write",
            "pbs",
            "NSServicesStatus",
            "-dict-add",
            "(null) - Explain selection - runWorkflowAsService",
            '{ "enabled_context_menu" = 1; "enabled_services_menu" = 1; '
            '"key_equivalent" = "@~e"; }',
        )
    ]


def test_set_shortcut_escapes_quotes_in_the_key() -> None:
    runner = FakeRunner()
    PbsServicesRegistrar(runner).set_shortcut("Explain selection", '@"')
    assert '"key_equivalent" = "@\\"";' in runner.calls[0][-1]


def test_refresh_flushes_then_updates_pbs() -> None:
    runner = FakeRunner()
    PbsServicesRegistrar(runner).refresh()
    assert runner.calls == [(PBS, "-flush"), (PBS, "-update")]


def test_read_status_returns_the_defaults_output() -> None:
    runner = FakeRunner(queue=[CommandResult(0, '{ "(null) - Explain selection" = ...; }', "")])
    status = PbsServicesRegistrar(runner).read_status()
    assert status == '{ "(null) - Explain selection" = ...; }'
    assert runner.calls == [STATUS_ARGS]


def test_a_failing_command_is_an_install_error_carrying_its_stderr() -> None:
    runner = FakeRunner(queue=[CommandResult(1, "", "Domain pbs does not exist\n")])
    with pytest.raises(InstallError, match=r"^defaults read failed: Domain pbs does not exist$"):
        PbsServicesRegistrar(runner).read_status()


def test_a_silent_failure_reports_the_exit_code() -> None:
    runner = FakeRunner(queue=[CommandResult(3, "", "")])
    with pytest.raises(
        InstallError, match=r"^/System/Library/CoreServices/pbs -flush failed: exit 3$"
    ):
        PbsServicesRegistrar(runner).refresh()


def test_a_missing_binary_is_an_install_error() -> None:
    with pytest.raises(InstallError, match=r"^defaults not found$"):
        PbsServicesRegistrar(_MissingBinaryRunner()).read_status()
