"""The ``explain-selection`` command line; the only module allowed to print."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Final, TextIO

DISTRIBUTION: Final[str] = "explain-selection"
UNKNOWN_VERSION: Final[str] = "unknown"


def package_version() -> str:
    """The installed distribution's version, or ``unknown`` outside an installed package."""
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return UNKNOWN_VERSION


def build_parser() -> argparse.ArgumentParser:
    """The argument parser: one ``version`` subcommand for now."""
    parser = argparse.ArgumentParser(
        prog=DISTRIBUTION,
        description="Send a terminal selection to a running Claude Code session.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("version", help="print the installed package version")
    return parser


def run(argv: Sequence[str], out: TextIO) -> int:
    """Run one subcommand, writing to ``out``; returns the exit code."""
    args = build_parser().parse_args(argv)
    command: str = args.command
    if command == "version":
        print(package_version(), file=out)
        return 0
    return 2


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.cli``."""
    return run(sys.argv[1:], sys.stdout)


__all__ = ["DISTRIBUTION", "build_parser", "main", "package_version", "run"]

if __name__ == "__main__":
    sys.exit(main())
