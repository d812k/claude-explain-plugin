"""MacServicesProbe: the macOS-only facts the doctor reports.

The bundle is a plain ``stat`` under ``~/Library/Services``; the shortcut status comes from
``defaults read pbs NSServicesStatus`` through the injected runner; ``osascript`` is looked
up on ``PATH``. Every failure reads as "absent" rather than raising: the doctor reports.
"""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from explain_selection.adapters.file_inspector import LocalFileInspector
from explain_selection.adapters.pbs import PbsServicesRegistrar
from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.domain import FileFacts
from explain_selection.errors import InstallError
from explain_selection.services import BUNDLE_NAME


@dataclass(frozen=True, slots=True)
class MacServicesProbe:
    """Implements the ``MacProbe`` protocol for a real Mac; ``which`` is injectable for tests."""

    runner: CommandRunner
    services_dir: Path
    timeout_s: float = field(default=10.0, kw_only=True)
    which: Callable[[str], str | None] = field(default=shutil.which, kw_only=True)

    def bundle(self) -> FileFacts:
        return LocalFileInspector().inspect(self.services_dir / BUNDLE_NAME)

    def shortcut_status(self) -> str | None:
        try:
            return PbsServicesRegistrar(self.runner, timeout_s=self.timeout_s).read_status()
        except InstallError:
            return None

    def osascript_found(self) -> bool:
        return self.which("osascript") is not None


__all__ = ["MacServicesProbe"]
