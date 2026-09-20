"""The plugin manifest and hooks file agree with pyproject and point at real wrappers."""

import re
import stat
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

REPO = Path(__file__).resolve().parents[2]
WRAPPER_REF = re.compile(r'^"\$\{CLAUDE_PLUGIN_ROOT\}/(bin/[\w-]+)"$')
HOOK_TIMEOUT_S = 5


class _Command(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["command"]
    command: str
    timeout: int


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matcher: str | None = None
    hooks: list[_Command]


class _HooksFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    hooks: dict[str, list[_Group]]


class _Author(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    description: str
    author: _Author
    hooks: str


def _manifest() -> _Manifest:
    return _Manifest.model_validate_json((REPO / ".claude-plugin" / "plugin.json").read_text())


def _hooks_file() -> _HooksFile:
    return _HooksFile.model_validate_json((REPO / "hooks" / "hooks.json").read_text())


def _pyproject_version() -> str:
    with (REPO / "pyproject.toml").open("rb") as handle:
        project: dict[str, str] = tomllib.load(handle)["project"]
    return project["version"]


def _commands() -> dict[str, list[str]]:
    hooks = _hooks_file().hooks
    return {event: [c.command for g in groups for c in g.hooks] for event, groups in hooks.items()}


def test_manifest_names_the_plugin_and_matches_pyproject_version() -> None:
    manifest = _manifest()
    assert manifest.name == "explain-selection"
    assert manifest.version == _pyproject_version()
    assert manifest.description
    assert manifest.author.name


def test_manifest_points_at_the_hooks_file() -> None:
    assert _manifest().hooks == "./hooks/hooks.json"
    assert (REPO / "hooks" / "hooks.json").is_file()


def test_hooks_cover_exactly_the_three_lifecycle_events() -> None:
    assert set(_commands()) == {"SessionStart", "CwdChanged", "SessionEnd"}


def test_each_event_has_one_command_hook_with_the_hook_timeout() -> None:
    for groups in _hooks_file().hooks.values():
        assert len(groups) == 1
        assert len(groups[0].hooks) == 1
        assert groups[0].hooks[0].timeout == HOOK_TIMEOUT_S


def test_start_and_cwd_register_while_end_unregisters() -> None:
    commands = _commands()
    register = '"${CLAUDE_PLUGIN_ROOT}/bin/explain-selection-register"'
    unregister = '"${CLAUDE_PLUGIN_ROOT}/bin/explain-selection-unregister"'
    assert commands["SessionStart"] == [register]
    assert commands["CwdChanged"] == [register]
    assert commands["SessionEnd"] == [unregister]


def test_every_referenced_wrapper_exists_and_is_executable() -> None:
    for commands in _commands().values():
        for command in commands:
            match = WRAPPER_REF.match(command)
            assert match is not None
            wrapper = REPO / match.group(1)
            assert wrapper.is_file()
            assert wrapper.stat().st_mode & stat.S_IXUSR
