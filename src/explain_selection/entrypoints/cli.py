"""The ``explain-selection`` command line; the only module allowed to print.

Subcommands: ``version``; ``sessions`` (one line per live session, of either kind); and
``send --pid <int> [--text -|<string>]`` (post text verbatim, from stdin when ``--text`` is
``-`` or absent). Exit codes: 0 success; 1 the send failed or there is no such session, with
the reason on stderr; 2 usage.
"""

import argparse
import logging
import os
import sys
from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Final, TextIO, assert_never

from explain_selection.domain import Pid, describe_target
from explain_selection.entrypoints.runtime import (
    checkout_root,
    configure_logging,
    entrypoint_logger,
    read_stdin,
)
from explain_selection.services import (
    NoSuchSession,
    SendDeps,
    Sent,
    SessionSummary,
    Unavailable,
    list_sessions,
    send_message,
)

logger = logging.getLogger(__name__)

DISTRIBUTION: Final[str] = "explain-selection"
UNKNOWN_VERSION: Final[str] = "unknown"
STDIN_MARKER: Final[str] = "-"
SEND_USAGE: Final[str] = "usage: explain-selection send --pid <int> [--text -|<string>]"
EXIT_OK: Final[int] = 0
EXIT_FAILED: Final[int] = 1
EXIT_USAGE: Final[int] = 2
_ALIGNED_COLUMNS: Final[int] = 5


def package_version() -> str:
    """The installed distribution's version, or ``unknown`` outside an installed package."""
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_parser() -> argparse.ArgumentParser:
    """The argument parser: ``version``, ``sessions`` and ``send``."""
    parser = argparse.ArgumentParser(
        prog=DISTRIBUTION,
        description="Send a terminal selection to a running Claude Code session.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("version", help="print the installed package version")
    subcommands.add_parser("sessions", help="list the live Claude Code sessions of either kind")
    send = subcommands.add_parser("send", help="post text verbatim into one session's inbox")
    send.add_argument(
        "--pid", type=int, required=True, help="pid of the target session (see `sessions`)"
    )
    send.add_argument(
        "--text",
        default=STDIN_MARKER,
        help="the text to send, or `-` (the default) to read it from stdin",
    )
    return parser


def run(
    argv: Sequence[str],
    stdin_text: Callable[[], str],
    build_deps: Callable[[], SendDeps],
    out: TextIO,
    err: TextIO,
) -> int:
    """Run one subcommand, printing to ``out`` and ``err``; returns the exit code.

    ``build_deps`` runs only for ``sessions`` and ``send``, once argv has parsed, so
    ``version`` and usage errors never read settings, open the log or start a subprocess.
    """
    args = build_parser().parse_args(argv)
    command: str = args.command
    if command == "version":
        print(package_version(), file=out)
        return EXIT_OK
    try:
        deps = build_deps()
    except Exception as error:
        logger.exception("cli could not start")
        print(f"{DISTRIBUTION}: could not start: {error}", file=err)
        return EXIT_FAILED
    try:
        if command == "sessions":
            return _sessions(deps, out, err)
        if command == "send":
            pid: int = args.pid
            text: str = args.text
            content = stdin_text() if text == STDIN_MARKER else text
            return _send(Pid(pid), content, deps, out, err)
    except Exception as error:
        logger.exception("%s failed", command)
        print(f"{DISTRIBUTION}: {error}", file=err)
        return EXIT_FAILED
    return EXIT_USAGE


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.cli``."""
    return run(sys.argv[1:], read_stdin, _build_deps, sys.stdout, sys.stderr)


def _build_deps() -> SendDeps:
    from explain_selection.adapters import SubprocessRunner
    from explain_selection.entrypoints.deps import build_send_deps, current_process
    from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

    environ = dict(os.environ)
    settings = load_settings(environ, resolve_plugin_root(environ, checkout_root()))
    configure_logging(settings.log_file, entrypoint_logger())
    return build_send_deps(settings, environ, current_process(), SubprocessRunner())


def format_sessions(summaries: Sequence[SessionSummary]) -> list[str]:
    """``pid  status  kind  registered|unregistered  label  cwd``, all but ``cwd`` aligned."""
    rows = [
        (
            str(s.pid),
            s.status.value,
            s.kind.value,
            "registered" if s.registered else "unregistered",
            s.label,
            s.cwd,
        )
        for s in summaries
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(_ALIGNED_COLUMNS)]
    return [
        "  ".join(
            [
                *(cell.ljust(w) for cell, w in zip(row[:_ALIGNED_COLUMNS], widths, strict=True)),
                row[_ALIGNED_COLUMNS],
            ]
        )
        for row in rows
    ]


def _sessions(deps: SendDeps, out: TextIO, err: TextIO) -> int:
    summaries = list_sessions(deps)
    if not summaries:
        print("No live Claude Code sessions.", file=err)
        return EXIT_OK
    for line in format_sessions(summaries):
        print(line, file=out)
    return EXIT_OK


def _send(pid: Pid, content: str, deps: SendDeps, out: TextIO, err: TextIO) -> int:
    if not content.strip():
        print(f"{SEND_USAGE}; the text is empty", file=err)
        return EXIT_USAGE
    result = send_message(pid, content, deps)
    match result:
        case Sent(target=target, chars=chars):
            print(f"Sent {chars} characters to {describe_target(target)}.", file=out)
            return EXIT_OK
        case NoSuchSession(pid=missing):
            print(
                f"{DISTRIBUTION}: no live session with pid {missing}; "
                f"run `{DISTRIBUTION} sessions` to list them",
                file=err,
            )
            return EXIT_FAILED
        case Unavailable(pid=unreachable, reason=reason):
            print(f"{DISTRIBUTION}: could not reach pid {unreachable}: {reason}", file=err)
            return EXIT_FAILED
        case _:
            assert_never(result)


__all__ = [
    "DISTRIBUTION",
    "EXIT_FAILED",
    "EXIT_OK",
    "EXIT_USAGE",
    "SEND_USAGE",
    "build_parser",
    "format_sessions",
    "main",
    "package_version",
    "run",
]

if __name__ == "__main__":
    sys.exit(main())
