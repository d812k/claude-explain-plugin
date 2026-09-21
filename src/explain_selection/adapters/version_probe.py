"""VenvVersionProbe: asks the runtime venv's Python which version of this package it holds.

The doctor compares that against the plugin manifest; a mismatch means the bootstrap has
not been rerun since the checkout changed.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.errors import SubprocessError

logger = logging.getLogger(__name__)

# The distribution name from pyproject.toml; the venv installs this package under it.
DISTRIBUTION: Final[str] = "explain-selection"
_SCRIPT: Final[str] = f"import importlib.metadata as m; print(m.version({DISTRIBUTION!r}))"


@dataclass(frozen=True, slots=True)
class VenvVersionProbe:
    """Runs ``<python> -c`` through the injected runner; any failure reads as ``None``."""

    runner: CommandRunner
    timeout_s: float = field(default=10.0, kw_only=True)

    def installed_version(self, python: Path) -> str | None:
        try:
            result = self.runner.run([str(python), "-c", _SCRIPT], timeout=self.timeout_s)
        except SubprocessError as exc:
            logger.warning("could not query the venv version: %s", exc)
            return None
        if result.returncode != 0:
            logger.warning(
                "the venv has no %s installed (exit %d)", DISTRIBUTION, result.returncode
            )
            return None
        return result.stdout.strip() or None


__all__ = ["DISTRIBUTION", "VenvVersionProbe"]
