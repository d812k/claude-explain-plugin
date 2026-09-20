"""Composition root: assemble the service dependency bundles from Settings.

Each ``main()`` calls :func:`current_process` once and hands the result down; this is the
only module that reads process identity from the interpreter. The command runner is a
parameter so tests can wire the real adapters over a fake runner.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from explain_selection.adapters import (
    AgentsCli,
    CommandRunner,
    FileTargetMemory,
    InboxSocketPoster,
    OpenLinkOpener,
    OsascriptChooser,
    OsascriptFocus,
    OsProcessProbe,
    PsTtyLookup,
    RegistryFiles,
    SystemClock,
    TempFiles,
    TmuxAwareFocus,
    TmuxPanes,
    UnixSocketConnector,
)
from explain_selection.entrypoints.settings import Settings
from explain_selection.services import DeliverDeps, RegisterDeps


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Identity of the running process that adapters need."""

    uid: int


def current_process() -> ProcessInfo:
    """Read the process identity once, at the entrypoint."""
    return ProcessInfo(uid=os.getuid())


def build_register_deps(settings: Settings, runner: CommandRunner) -> RegisterDeps:
    """Dependencies for the SessionStart, CwdChanged and SessionEnd hooks."""
    return RegisterDeps(
        clock=SystemClock(),
        registry=RegistryFiles(settings.sessions_dir),
        tty_lookup=PsTtyLookup(runner),
    )


def build_deliver_deps(
    settings: Settings,
    environ: Mapping[str, str],
    process: ProcessInfo,
    runner: CommandRunner,
) -> DeliverDeps:
    """Dependencies for the hotkey capture path."""
    return DeliverDeps(
        clock=SystemClock(),
        sessions=AgentsCli(runner),
        registry=RegistryFiles(settings.sessions_dir),
        focus=TmuxAwareFocus(OsascriptFocus(runner), TmuxPanes(runner)),
        memory=FileTargetMemory(settings.last_target_file),
        poster=InboxSocketPoster(UnixSocketConnector(), environ, process.uid),
        chooser=OsascriptChooser(runner),
        opener=OpenLinkOpener(runner),
        tempfiles=TempFiles(settings.temp_dir),
        probe=OsProcessProbe(),
    )


__all__ = ["ProcessInfo", "build_deliver_deps", "build_register_deps", "current_process"]
