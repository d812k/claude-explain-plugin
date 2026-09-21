"""The ``install`` subcommand's pieces: its arguments, its context, and its report lines.

``cli.py`` stays the dispatcher and the only module that prints; this module turns parsed
arguments plus process context into an :class:`InstallPlan` and a report into lines.
"""

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from explain_selection.entrypoints.runtime import checkout_root
from explain_selection.services import InstallDeps, InstallPlan, InstallReport, Platform

DEFAULT_SHORTCUT: Final[str] = "@~e"
_MODIFIERS: Final[dict[str, str]] = {
    "@": "Command",
    "~": "Option",
    "^": "Control",
    "$": "Shift",
}


@dataclass(frozen=True, slots=True)
class InstallContext:
    """What ``install`` learns from the process: paths, platform and adapters."""

    home: Path
    plugin_root: Path
    venv_python: Path
    platform: Platform
    deps: InstallDeps


def configure_install_parser(install: argparse.ArgumentParser) -> None:
    """Add ``--shortcut``, ``--dry-run`` and ``--plugin-root`` to the ``install`` subparser."""
    install.add_argument(
        "--shortcut",
        default=DEFAULT_SHORTCUT,
        help="Services key equivalent: @ command, ~ option, ^ control, $ shift, then the key "
        "(default: %(default)s, Command-Option-E)",
    )
    install.add_argument(
        "--dry-run", action="store_true", help="report what would happen and touch nothing"
    )
    install.add_argument(
        "--plugin-root",
        type=Path,
        default=None,
        help="the plugin checkout (default: $EXPLAIN_SELECTION_PLUGIN_ROOT, else this checkout)",
    )


def plan_from(args: argparse.Namespace, context: InstallContext) -> InstallPlan:
    """Combine the parsed ``install`` arguments with the process context."""
    shortcut: str = args.shortcut
    dry_run: bool = args.dry_run
    plugin_root: Path | None = args.plugin_root
    return InstallPlan(
        home=context.home,
        plugin_root=plugin_root if plugin_root is not None else context.plugin_root,
        venv_python=context.venv_python,
        shortcut=shortcut,
        platform=context.platform,
        dry_run=dry_run,
    )


def describe_shortcut(key: str) -> str:
    """``@~e`` becomes ``Command-Option-E``; a key with no character is kept as typed."""
    names: list[str] = []
    rest = key
    while rest and rest[0] in _MODIFIERS:
        names.append(_MODIFIERS[rest[0]])
        rest = rest[1:]
    if not rest:
        return key
    return "-".join([*names, rest.upper()])


def report_lines(report: InstallReport, shortcut: str) -> list[str]:
    """One ``[status] name: detail`` line per step, then the next steps for the user."""
    return [
        *(f"[{step.status}] {step.name}: {step.detail}" for step in report.steps),
        "",
        "Next steps:",
        "  1. Relaunch your terminal apps so the shortcut registers.",
        f"  2. Select text and press {describe_shortcut(shortcut)} ({shortcut}).",
        "  3. The first time several Claude Code sessions are open, macOS asks to allow",
        "     controlling iTerm2 or Terminal; click Allow.",
        "  4. Run `explain-selection doctor` to check everything.",
    ]


def build_install_context(platform: Platform, venv_python: Path) -> InstallContext:
    """The real context: ``home`` from settings, local adapters, ``~/Library/Services``.

    File logging is deliberately not configured here: a dry run must touch nothing, and
    install reports on the console.
    """
    from explain_selection.adapters import (
        LocalInstallFiles,
        PbsServicesRegistrar,
        SubprocessRunner,
    )
    from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

    environ = dict(os.environ)
    plugin_root = resolve_plugin_root(environ, checkout_root())
    settings = load_settings(environ, plugin_root)
    user_home = Path(environ.get("HOME") or "/")
    return InstallContext(
        home=settings.home,
        plugin_root=plugin_root,
        venv_python=venv_python,
        platform=platform,
        deps=InstallDeps(
            files=LocalInstallFiles(),
            registrar=PbsServicesRegistrar(SubprocessRunner()),
            services_dir=user_home / "Library" / "Services",
        ),
    )


__all__ = [
    "DEFAULT_SHORTCUT",
    "InstallContext",
    "build_install_context",
    "configure_install_parser",
    "describe_shortcut",
    "plan_from",
    "report_lines",
]
