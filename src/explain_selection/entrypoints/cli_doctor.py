"""The ``doctor`` subcommand's pieces: its dependencies, the manifest version, and the lines.

``cli.py`` stays the dispatcher and the only module that prints; this module builds the
:class:`DoctorDeps` from the process and turns the checks into report lines. Doctor is
read-only: it configures no file logging, because that would create the very home
directory it is inspecting.
"""

import os
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, ValidationError

from explain_selection.domain import UNREADABLE_PLUGIN_VERSION, Check
from explain_selection.entrypoints.runtime import checkout_root
from explain_selection.services import DoctorDeps, Platform

# The plugin's name in .claude-plugin/plugin.json; enabledPlugins keys start with it.
PLUGIN_NAME: Final[str] = "explain-selection"
MANIFEST_RELATIVE: Final[Path] = Path(".claude-plugin") / "plugin.json"
_FIX_INDENT: Final[str] = "    fix: "


class _Manifest(BaseModel):
    """The one manifest field the doctor compares against."""

    model_config = ConfigDict(extra="ignore")

    version: str


def plugin_version_from(manifest: Path) -> str:
    """The manifest's ``version``, or :data:`UNREADABLE_PLUGIN_VERSION` when it cannot be read."""
    try:
        raw = manifest.read_text(encoding="utf-8")
    except OSError:
        return UNREADABLE_PLUGIN_VERSION
    try:
        return _Manifest.model_validate_json(raw).version
    except ValidationError:
        return UNREADABLE_PLUGIN_VERSION


def report_lines(checks: Sequence[Check]) -> list[str]:
    """``[status] name: detail`` per check, an indented ``fix:`` line after each non-ok one,
    then ``doctor: N ok, N warn, N fail, N skipped``."""
    lines: list[str] = []
    for check in checks:
        lines.append(f"[{check.status}] {check.name}: {check.detail}")
        if check.fix is not None:
            lines.append(f"{_FIX_INDENT}{check.fix}")
    counts = Counter(check.status for check in checks)
    lines.append(
        f"doctor: {counts['ok']} ok, {counts['warn']} warn, {counts['fail']} fail, "
        f"{counts['skip']} skipped"
    )
    return lines


def claude_settings_paths(user_home: Path, cwd: Path) -> tuple[Path, Path, Path]:
    """User, project and local ``settings.json``, in override order."""
    return (
        user_home / ".claude" / "settings.json",
        cwd / ".claude" / "settings.json",
        cwd / ".claude" / "settings.local.json",
    )


def build_doctor_deps(platform: Platform, user_home: Path, cwd: Path) -> DoctorDeps:
    """The real dependencies: settings for the paths, local adapters, the manifest version."""
    from explain_selection.adapters import (
        AgentsCli,
        JsonClaudeSettingsReader,
        LocalFileInspector,
        MacServicesProbe,
        OsProcessProbe,
        RegistryFiles,
        SubprocessRunner,
        SystemClock,
        VenvVersionProbe,
    )
    from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

    environ = dict(os.environ)
    plugin_root = resolve_plugin_root(environ, checkout_root())
    settings = load_settings(environ, plugin_root)
    runner = SubprocessRunner()
    services_dir = user_home / "Library" / "Services"
    return DoctorDeps(
        files=LocalFileInspector(),
        sessions=AgentsCli(runner),
        registry=RegistryFiles(settings.sessions_dir),
        process=OsProcessProbe(),
        clock=SystemClock(),
        versions=VenvVersionProbe(runner),
        claude_settings=JsonClaudeSettingsReader(
            claude_settings_paths(user_home, cwd), PLUGIN_NAME
        ),
        mac=MacServicesProbe(runner, services_dir) if platform == "darwin" else None,
        home=settings.home,
        plugin_root=plugin_root,
        plugin_version=plugin_version_from(plugin_root / MANIFEST_RELATIVE),
        template_path=settings.prompt_template,
    )


__all__ = [
    "MANIFEST_RELATIVE",
    "PLUGIN_NAME",
    "build_doctor_deps",
    "claude_settings_paths",
    "plugin_version_from",
    "report_lines",
]
