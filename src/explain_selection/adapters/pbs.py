"""``ServicesRegistrar`` for macOS: ``defaults`` and ``pbs`` through the injected runner.

The Services menu keeps its per-service state in the ``pbs`` defaults domain; a workflow
service is keyed ``(null) - <menu title> - runWorkflowAsService``. Only the argument lists
are unit-tested; the commands themselves exist only on a Mac.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.errors import InstallError, SubprocessError

PBS: Final[str] = "/System/Library/CoreServices/pbs"
_DEFAULTS: Final[str] = "defaults"
_DOMAIN: Final[str] = "pbs"
_KEY: Final[str] = "NSServicesStatus"
_MESSAGE: Final[str] = "runWorkflowAsService"
_NAMED_ARGS: Final[int] = 2


def _plist_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


@dataclass(frozen=True, slots=True)
class PbsServicesRegistrar:
    """Assigns a Services shortcut with ``defaults write`` and reloads it with ``pbs``."""

    runner: CommandRunner
    timeout_s: float = field(default=10.0, kw_only=True)

    def set_shortcut(self, service_name: str, key: str) -> None:
        entry = f"(null) - {service_name} - {_MESSAGE}"
        value = (
            '{ "enabled_context_menu" = 1; "enabled_services_menu" = 1; '
            f'"key_equivalent" = "{_plist_string(key)}"; }}'
        )
        self._run([_DEFAULTS, "write", _DOMAIN, _KEY, "-dict-add", entry, value])

    def refresh(self) -> None:
        self._run([PBS, "-flush"])
        self._run([PBS, "-update"])

    def read_status(self) -> str:
        return self._run([_DEFAULTS, "read", _DOMAIN, _KEY])

    def _run(self, args: Sequence[str]) -> str:
        try:
            result = self.runner.run(args, timeout=self.timeout_s)
        except SubprocessError as exc:
            raise InstallError(str(exc)) from exc
        if result.returncode != 0:
            reason = result.stderr.strip() or f"exit {result.returncode}"
            raise InstallError(f"{' '.join(args[:_NAMED_ARGS])} failed: {reason}")
        return result.stdout


__all__ = ["PBS", "PbsServicesRegistrar"]
