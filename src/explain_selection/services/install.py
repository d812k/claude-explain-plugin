"""The install use case: lay out the runtime home and, on macOS, register the Services entry.

Install does the heavy work once so the hotkey path only execs a shim. Every step reports what
it did; a failing step is recorded and the remaining steps still run, so one report shows the
user everything that needs attention. With ``dry_run`` nothing is touched.
"""

import shlex
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from explain_selection.errors import InstallError
from explain_selection.services.protocols import InstallFiles, ServicesRegistrar

type Platform = Literal["darwin", "other"]
type StepStatus = Literal["done", "skipped", "planned", "failed"]

SERVICE_NAME: Final[str] = "Explain selection"
BUNDLE_NAME: Final[str] = f"{SERVICE_NAME}.workflow"
CONFIG_FILE: Final[str] = "config.env"
PROMPT_FILE: Final[str] = "explain-prompt.txt"
SHIM_FILE: Final[str] = "capture"
MANUAL_SHORTCUT_HINT: Final[str] = (
    "set it manually: System Settings > Keyboard > Keyboard Shortcuts > Services > Text > "
    f"{SERVICE_NAME}"
)
MACOS_ONLY: Final[str] = "macOS only"
PRIVATE_FILE_MODE: Final[int] = 0o600
EXECUTABLE_MODE: Final[int] = 0o700
_TEMPLATE_RELATIVE: Final[Path] = Path("templates") / PROMPT_FILE
_BUNDLE_RELATIVE: Final[Path] = Path("assets") / BUNDLE_NAME
_CONFIG_HEADER: Final[str] = """\
# explain-selection settings. Lines starting with # are comments; the environment wins.
# Available settings and their defaults:
#   EXPLAIN_SELECTION_HOME=$HOME/.claude/explain-selection
#       (environment only: this file lives under it)
#   EXPLAIN_SELECTION_MAX_CHARS=200000
#   EXPLAIN_SELECTION_LONG_SELECTION=truncate
#       (truncate or tempfile)
#   EXPLAIN_SELECTION_PROMPT_TEMPLATE=<plugin root>/templates/explain-prompt.txt
#   EXPLAIN_SELECTION_REMEMBER_TARGET_MINUTES=10
#   EXPLAIN_SELECTION_FALLBACK_CWD=$HOME
"""


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Everything install needs to know, resolved once at the entrypoint."""

    home: Path
    plugin_root: Path
    venv_python: Path
    shortcut: str
    platform: Platform
    dry_run: bool

    @property
    def config_file(self) -> Path:
        """``<home>/config.env``, written once and then left to the user."""
        return self.home / CONFIG_FILE

    @property
    def prompt_file(self) -> Path:
        """``<home>/explain-prompt.txt``, the user-editable copy of the template."""
        return self.home / PROMPT_FILE

    @property
    def shim_file(self) -> Path:
        """``<home>/capture``, what the hotkey execs."""
        return self.home / SHIM_FILE

    @property
    def template_source(self) -> Path:
        """The shipped prompt template inside the plugin."""
        return self.plugin_root / _TEMPLATE_RELATIVE

    @property
    def bundle_source(self) -> Path:
        """The shipped Automator bundle inside the plugin."""
        return self.plugin_root / _BUNDLE_RELATIVE


@dataclass(frozen=True, slots=True)
class StepResult:
    """One install step's outcome, in the order the steps ran."""

    name: str
    status: StepStatus
    detail: str


@dataclass(frozen=True, slots=True)
class InstallReport:
    """Every step's result; ``ok`` when none failed."""

    steps: tuple[StepResult, ...]

    @property
    def ok(self) -> bool:
        """``True`` unless some step failed; skipped and planned steps are fine."""
        return all(step.status != "failed" for step in self.steps)


@dataclass(frozen=True, slots=True)
class InstallDeps:
    """Adapters for the install use case plus where macOS looks for user Services."""

    files: InstallFiles
    registrar: ServicesRegistrar
    services_dir: Path


type _Outcome = tuple[StepStatus, str]
type _Step = Callable[[InstallPlan, InstallDeps], _Outcome]


def platform_from(sys_platform: str) -> Platform:
    """Map ``sys.platform`` to the two cases install distinguishes."""
    return "darwin" if sys_platform == "darwin" else "other"


def config_content(home: Path) -> str:
    """The initial ``config.env``: every setting documented, the template pointed at ``home``."""
    return f"{_CONFIG_HEADER}EXPLAIN_SELECTION_PROMPT_TEMPLATE={home / PROMPT_FILE}\n"


def shim_content(plugin_root: Path, venv_python: Path) -> str:
    """The capture shim: export the plugin root and exec the venv's Python entrypoint.

    Both paths are shell-quoted, so spaces and ``$`` in them survive ``sh`` verbatim.
    """
    return (
        "#!/bin/sh\n"
        f"EXPLAIN_SELECTION_PLUGIN_ROOT={shlex.quote(str(plugin_root))}\n"
        "export EXPLAIN_SELECTION_PLUGIN_ROOT\n"
        f'exec {shlex.quote(str(venv_python))} -m explain_selection.entrypoints.capture "$@"\n'
    )


def install_plugin(plan: InstallPlan, deps: InstallDeps) -> InstallReport:
    """Run every install step in order, recording failures instead of stopping."""
    return InstallReport(steps=tuple(_guarded(name, step, plan, deps) for name, step in _STEPS))


def _guarded(name: str, step: _Step, plan: InstallPlan, deps: InstallDeps) -> StepResult:
    try:
        status, detail = step(plan, deps)
    except InstallError as error:
        return StepResult(name=name, status="failed", detail=str(error))
    return StepResult(name=name, status=status, detail=detail)


def _home(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    if plan.dry_run:
        return "planned", f"would create {plan.home} with mode 0700"
    deps.files.ensure_private_dir(plan.home)
    return "done", f"{plan.home} (mode 0700)"


def _config(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    def write() -> None:
        deps.files.write_private_file(
            plan.config_file, config_content(plan.home), PRIVATE_FILE_MODE
        )

    return _write_once(plan, deps, plan.config_file, write)


def _prompt(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    def write() -> None:
        deps.files.copy_file(plan.template_source, plan.prompt_file)

    return _write_once(plan, deps, plan.prompt_file, write)


def _write_once(
    plan: InstallPlan, deps: InstallDeps, path: Path, write: Callable[[], None]
) -> _Outcome:
    if deps.files.exists(path):
        if plan.dry_run:
            return "planned", f"would keep existing {path}"
        return "skipped", f"{path} exists; kept"
    if plan.dry_run:
        return "planned", f"would write {path}"
    write()
    return "done", f"wrote {path}"


def _shim(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    if plan.dry_run:
        return "planned", f"would write {plan.shim_file} (mode 0700)"
    content = shim_content(plan.plugin_root, plan.venv_python)
    deps.files.write_private_file(plan.shim_file, content, EXECUTABLE_MODE)
    return "done", f"wrote {plan.shim_file} (mode 0700)"


def _service(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    if plan.platform != "darwin":
        return "skipped", MACOS_ONLY
    target = deps.services_dir / BUNDLE_NAME
    if plan.dry_run:
        return "planned", f"would install {target}"
    deps.files.replace_tree(plan.bundle_source, target)
    return "done", f"installed {target}"


def _shortcut(plan: InstallPlan, deps: InstallDeps) -> _Outcome:
    if plan.platform != "darwin":
        return "skipped", MACOS_ONLY
    if plan.dry_run:
        return "planned", f"would assign {plan.shortcut} to {SERVICE_NAME} and refresh Services"
    try:
        deps.registrar.set_shortcut(SERVICE_NAME, plan.shortcut)
        deps.registrar.refresh()
        status = deps.registrar.read_status()
    except InstallError as error:
        return "failed", f"{error}; {MANUAL_SHORTCUT_HINT}"
    if SERVICE_NAME not in status:
        return "failed", MANUAL_SHORTCUT_HINT
    return "done", f"{plan.shortcut} assigned to {SERVICE_NAME}"


_STEPS: Final[tuple[tuple[str, _Step], ...]] = (
    ("home", _home),
    ("config", _config),
    ("prompt", _prompt),
    ("shim", _shim),
    ("service", _service),
    ("shortcut", _shortcut),
)

__all__ = [
    "BUNDLE_NAME",
    "MANUAL_SHORTCUT_HINT",
    "SERVICE_NAME",
    "InstallDeps",
    "InstallPlan",
    "InstallReport",
    "Platform",
    "StepResult",
    "StepStatus",
    "config_content",
    "install_plugin",
    "platform_from",
    "shim_content",
]
