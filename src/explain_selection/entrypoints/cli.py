"""The ``explain-selection`` command line; the only module allowed to print.

Subcommands: ``version``; ``sessions`` (one line per live session, of either kind);
``send --pid <int> [--text -|<string>]`` (post text verbatim, from stdin when ``--text`` is
``-`` or absent); ``install [--shortcut KEY] [--dry-run] [--plugin-root PATH]`` (lay out
the runtime home and, on macOS, register the Services entry; one ``[status] step: detail``
line per step); and ``doctor`` (one ``[status] name: detail`` line per check, an indented
``fix:`` line after each warn or fail, then a summary). Exit codes: 0 success; 1 the send
failed, there is no such session, an install step failed or a doctor check failed, with the
reason on stderr or in the line; 2 usage.
"""

import argparse
import functools
import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final, TextIO, assert_never

from explain_selection.domain import Pid, checks_ok, describe_target
from explain_selection.entrypoints.cli_doctor import build_doctor_deps
from explain_selection.entrypoints.cli_doctor import report_lines as doctor_lines
from explain_selection.entrypoints.cli_install import (
    InstallContext,
    build_install_context,
    configure_install_parser,
    plan_from,
    report_lines,
)
from explain_selection.entrypoints.runtime import (
    checkout_root,
    configure_logging,
    entrypoint_logger,
    read_stdin,
)
from explain_selection.services import (
    DoctorDeps,
    NoSuchSession,
    SendDeps,
    Sent,
    SessionSummary,
    Unavailable,
    install_plugin,
    list_sessions,
    platform_from,
    run_doctor,
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
    """The argument parser: ``version``, ``sessions``, ``send``, ``install`` and ``doctor``."""
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
    install = subcommands.add_parser(
        "install", help="set up the runtime home and, on macOS, the Services shortcut"
    )
    configure_install_parser(install)
    subcommands.add_parser(
        "doctor", help="check the install and every live session; exit 1 on a failure"
    )
    return parser


@dataclass(frozen=True, slots=True)
class CliDeps:
    """Lazy access to the process; each builder runs only for the subcommand that needs it.

    ``build_send_deps`` serves ``sessions`` and ``send``; ``build_install`` serves ``install``;
    ``build_doctor`` serves ``doctor``. All run after argv has parsed, so ``version`` and usage
    errors never read settings, open the log or start a subprocess.
    """

    stdin_text: Callable[[], str]
    build_send_deps: Callable[[], SendDeps]
    build_install: Callable[[], InstallContext]
    build_doctor: Callable[[], DoctorDeps]


def run(argv: Sequence[str], deps: CliDeps, out: TextIO, err: TextIO) -> int:
    """Run one subcommand, printing to ``out`` and ``err``; returns the exit code."""
    args = build_parser().parse_args(argv)
    command: str = args.command
    if command == "version":
        print(package_version(), file=out)
        return EXIT_OK
    if command == "install":
        return _install(args, deps.build_install, out, err)
    if command == "doctor":
        return _doctor(deps.build_doctor, out, err)
    try:
        send_deps = deps.build_send_deps()
    except Exception as error:
        return _could_not_start(error, err)
    try:
        return _dispatch(args, send_deps, deps.stdin_text, out, err)
    except Exception as error:
        logger.exception("%s failed", command)
        print(f"{DISTRIBUTION}: {error}", file=err)
        return EXIT_FAILED


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.cli``."""
    deps = CliDeps(
        stdin_text=read_stdin,
        build_send_deps=_build_deps,
        build_install=functools.partial(
            build_install_context, platform_from(sys.platform), Path(sys.executable)
        ),
        build_doctor=functools.partial(
            build_doctor_deps, platform_from(sys.platform), Path.home(), Path.cwd()
        ),
    )
    return run(sys.argv[1:], deps, sys.stdout, sys.stderr)


def _dispatch(
    args: argparse.Namespace,
    send_deps: SendDeps,
    stdin_text: Callable[[], str],
    out: TextIO,
    err: TextIO,
) -> int:
    command: str = args.command
    if command == "sessions":
        return _sessions(send_deps, out, err)
    if command == "send":
        pid: int = args.pid
        text: str = args.text
        content = stdin_text() if text == STDIN_MARKER else text
        return _send(Pid(pid), content, send_deps, out, err)
    return EXIT_USAGE


def _could_not_start(error: Exception, err: TextIO) -> int:
    logger.exception("cli could not start")
    print(f"{DISTRIBUTION}: could not start: {error}", file=err)
    return EXIT_FAILED


def _install(
    args: argparse.Namespace, build_install: Callable[[], InstallContext], out: TextIO, err: TextIO
) -> int:
    try:
        context = build_install()
    except Exception as error:
        return _could_not_start(error, err)
    plan = plan_from(args, context)
    try:
        report = install_plugin(plan, context.deps)
    except Exception as error:
        logger.exception("install failed")
        print(f"{DISTRIBUTION}: {error}", file=err)
        return EXIT_FAILED
    for line in report_lines(report, plan.shortcut):
        print(line, file=out)
    return EXIT_OK if report.ok else EXIT_FAILED


def _doctor(build_doctor: Callable[[], DoctorDeps], out: TextIO, err: TextIO) -> int:
    try:
        doctor_deps = build_doctor()
    except Exception as error:
        return _could_not_start(error, err)
    try:
        checks = run_doctor(doctor_deps)
    except Exception as error:
        logger.exception("doctor failed")
        print(f"{DISTRIBUTION}: {error}", file=err)
        return EXIT_FAILED
    for line in doctor_lines(checks):
        print(line, file=out)
    return EXIT_OK if checks_ok(checks) else EXIT_FAILED


def _build_deps() -> SendDeps:
    from explain_selection.adapters import SubprocessRunner
    from explain_selection.entrypoints.deps import build_send_deps, current_process
    from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

    environ = dict(os.environ)
    settings = load_settings(environ, resolve_plugin_root(environ, checkout_root()))
    configure_logging(settings.log_file, entrypoint_logger())
    return build_send_deps(settings, environ, current_process(), SubprocessRunner())


def format_sessions(summaries: Sequence[SessionSummary]) -> list[str]:
    """``pid  status  kind  registered|unregistered  label  cwd``, all but ``cwd`` aligned.

    No sessions give no lines.
    """
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
    widths = [max((len(row[i]) for row in rows), default=0) for i in range(_ALIGNED_COLUMNS)]
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
    "CliDeps",
    "build_parser",
    "format_sessions",
    "main",
    "package_version",
    "run",
]

if __name__ == "__main__":
    sys.exit(main())
