"""Process-level helpers shared by every entrypoint's ``main()``: logging, paths, stdin."""

import logging
import sys
from pathlib import Path
from typing import Final

_LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"
PACKAGE_LOGGER: Final[str] = "explain_selection"


def configure_logging(log_file: Path, target: logging.Logger) -> None:
    """Send ``target``'s records to ``log_file`` (0600 inside a 0700 directory), never stdout."""
    log_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handler = logging.FileHandler(log_file)
    log_file.chmod(0o600)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    target.addHandler(handler)
    target.setLevel(logging.INFO)


def checkout_root() -> Path:
    """The repository root when running from a source checkout (``src/`` layout)."""
    return Path(__file__).resolve().parents[3]


def read_stdin() -> str:
    """All of stdin, or nothing when the process was started by hand from a terminal."""
    return "" if sys.stdin.isatty() else sys.stdin.read()


__all__ = ["PACKAGE_LOGGER", "checkout_root", "configure_logging", "read_stdin"]
