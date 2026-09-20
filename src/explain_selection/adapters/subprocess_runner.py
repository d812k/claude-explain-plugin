"""One place where this package shells out. Everything else takes a ``CommandRunner``.

Unit tests inject a fake runner; only :class:`SubprocessRunner` touches a real process, and it
is exercised only in integration tests. Commands are always an argument list with an explicit
timeout and never ``shell=True``.
"""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from explain_selection.errors import SubprocessError


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The outcome of one finished command; a non-zero ``returncode`` is not an error here."""

    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Runs one command to completion and returns its result."""

    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        """Run ``args`` with a hard ``timeout`` seconds; raise :class:`SubprocessError` if the
        process cannot be started or is killed on timeout."""
        ...


@dataclass(frozen=True, slots=True)
class SubprocessRunner:
    """The real runner: :func:`subprocess.run` with a timeout and an argument list."""

    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        argv = list(args)
        # Error messages name only the executable: the argument list may carry the selection
        # (deep link, notification text) and the messages end up in the log.
        name = argv[0] if argv else "?"
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SubprocessError(f"{name} timed out after {timeout:g} s") from exc
        except FileNotFoundError as exc:
            raise SubprocessError(f"{name} not found") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise SubprocessError(f"could not run {name}: {type(exc).__name__}") from exc
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["CommandResult", "CommandRunner", "SubprocessRunner"]
