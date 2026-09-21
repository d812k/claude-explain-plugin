"""The doctor use case: gather facts through the adapter protocols, then judge them.

``gather_facts`` is the only place that touches adapters; it reads and never writes, so a
doctor run leaves the registry and the runtime home exactly as it found them. The verdicts
come from the pure :func:`explain_selection.domain.evaluate`.
"""

import shlex
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

from explain_selection.domain import (
    TEXT_PLACEHOLDER,
    Check,
    ClaudeFacts,
    DoctorFacts,
    FileFacts,
    LiveSession,
    MacFacts,
    RegistryEntry,
    RootSource,
    RuntimeFacts,
    SessionFacts,
    evaluate,
    join_targets,
)
from explain_selection.errors import AgentsQueryError, SubprocessError
from explain_selection.services.install import CONFIG_FILE, SHIM_FILE
from explain_selection.services.protocols import (
    ClaudeSettingsReader,
    Clock,
    FileInspector,
    MacProbe,
    ProcessProbe,
    RegistryStore,
    SessionLister,
    VersionProbe,
)

VENV_PYTHON: Final[Path] = Path("venv") / "bin" / "python"
_SHIM_ROOT_PREFIX: Final[str] = "EXPLAIN_SELECTION_PLUGIN_ROOT="


@dataclass(frozen=True, slots=True)
class PluginRoot:
    """The plugin checkout the doctor compares against, and which record named it."""

    path: Path
    source: RootSource


@dataclass(frozen=True, slots=True)
class DoctorDeps:
    """Adapters plus the resolved paths and the plugin version the doctor compares against.

    ``mac`` is ``None`` off macOS, which turns the macOS checks into skips.
    """

    files: FileInspector
    sessions: SessionLister
    registry: RegistryStore
    process: ProcessProbe
    clock: Clock
    versions: VersionProbe
    claude_settings: ClaudeSettingsReader
    mac: MacProbe | None
    home: Path
    plugin_root: Path
    root_source: RootSource
    plugin_version: str
    template_path: Path


def run_doctor(deps: DoctorDeps) -> tuple[Check, ...]:
    """Gather every fact and return the checks in display order."""
    return evaluate(gather_facts(deps))


def gather_facts(deps: DoctorDeps) -> DoctorFacts:
    """Read the runtime home, Claude Code's state and, on macOS, the Services pieces."""
    return DoctorFacts(
        runtime=_runtime_facts(deps),
        claude=_claude_facts(deps),
        mac=_mac_facts(deps.mac),
    )


def _runtime_facts(deps: DoctorDeps) -> RuntimeFacts:
    files = deps.files
    python = deps.home / VENV_PYTHON
    python_facts = files.inspect(python)
    shim, shim_text = _inspect_and_read(files, deps.home / SHIM_FILE)
    template, template_text = _inspect_and_read(files, deps.template_path)
    return RuntimeFacts(
        home=files.inspect(deps.home),
        venv_python=python_facts,
        installed_version=deps.versions.installed_version(python) if python_facts.exists else None,
        plugin_version=deps.plugin_version,
        shim=shim,
        shim_plugin_root=_shim_plugin_root(shim_text),
        plugin_root=str(deps.plugin_root),
        root_source=deps.root_source,
        config_present=files.inspect(deps.home / CONFIG_FILE).exists,
        template_path=str(deps.template_path),
        template=template,
        template_has_placeholder=template_text is not None and TEXT_PLACEHOLDER in template_text,
    )


def _inspect_and_read(files: FileInspector, path: Path) -> tuple[FileFacts, str | None]:
    """``stat`` and read ``path``; a file that exists but yields no text is marked unreadable."""
    facts = files.inspect(path)
    text = files.read_text(path)
    if facts.exists and text is None:
        return replace(facts, readable=False), None
    return facts, text


def installed_plugin_root(files: FileInspector, home: Path, fallback: Path) -> PluginRoot:
    """The checkout the installed shim was written with, else ``fallback`` as the ``checkout``.

    A package installed into the runtime venv cannot infer its checkout from ``__file__``;
    the shim the installer wrote is the record of where the plugin was at install time.
    """
    recorded = _shim_plugin_root(files.read_text(home / SHIM_FILE))
    if recorded is None:
        return PluginRoot(path=fallback, source="checkout")
    return PluginRoot(path=Path(recorded), source="shim")


def _shim_plugin_root(text: str | None) -> str | None:
    if text is None:
        return None
    for line in text.splitlines():
        if line.startswith(_SHIM_ROOT_PREFIX):
            return _shell_word(line.removeprefix(_SHIM_ROOT_PREFIX))
    return None


def _shell_word(quoted: str) -> str | None:
    """The single word ``sh`` would assign from ``quoted``; ``None`` if it is not one word."""
    try:
        words = shlex.split(quoted)
    except ValueError:
        return None
    return words[0] if len(words) == 1 else None


def _claude_facts(deps: DoctorDeps) -> ClaudeFacts:
    live, agents_error = _live_sessions(deps.sessions)
    entries = deps.registry.read_all()
    live_pids = {session.pid for session in live}
    stale = sum(
        1
        for entry in entries
        if entry.pid not in live_pids and not deps.process.is_alive(entry.pid)
    )
    now = deps.clock.now_ms()
    targets = join_targets(live, entries, include_background=True)
    settings = deps.claude_settings.read()
    return ClaudeFacts(
        sessions=tuple(_session_facts(t.session, t.entry, now, deps.files) for t in targets),
        stale_entries=stale,
        cross_session_inbound=settings.cross_session_inbound,
        plugin_enabled=settings.plugin_enabled,
        unreadable_settings=settings.unreadable_files,
        agents_error=agents_error,
    )


def _live_sessions(sessions: SessionLister) -> tuple[tuple[LiveSession, ...], str | None]:
    try:
        return sessions.list_live(), None
    except (AgentsQueryError, SubprocessError) as error:
        return (), str(error)


def _session_facts(
    session: LiveSession, entry: RegistryEntry | None, now_ms: int, files: FileInspector
) -> SessionFacts:
    return SessionFacts(
        pid=session.pid,
        status=session.status,
        kind=session.kind,
        registered=entry is not None,
        tmux=None if entry is None else entry.tmux_pane or entry.tmux,
        socket=None if entry is None else files.inspect(Path(entry.socket)),
        age_ms=max(0, now_ms - session.started_at_ms),
    )


def _mac_facts(mac: MacProbe | None) -> MacFacts | None:
    if mac is None:
        return None
    return MacFacts(
        bundle=mac.bundle(),
        shortcut_status=mac.shortcut_status(),
        osascript_found=mac.osascript_found(),
    )


__all__ = [
    "VENV_PYTHON",
    "DoctorDeps",
    "PluginRoot",
    "gather_facts",
    "installed_plugin_root",
    "run_doctor",
]
