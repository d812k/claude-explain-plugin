"""Settings come from an explicit environ mapping and config.env; nothing reads os.environ."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from explain_selection.entrypoints.settings import (
    Settings,
    exported_plugin_root,
    load_settings,
    resolve_plugin_root,
)
from explain_selection.services import LongSelection

PLUGIN_ROOT = Path("/opt/plugin")


def _environ(home: Path, **extra: str) -> dict[str, str]:
    return {"HOME": str(home), **extra}


def test_defaults_derive_from_home_and_plugin_root(tmp_path: Path) -> None:
    settings = load_settings(_environ(tmp_path), PLUGIN_ROOT)
    assert settings.home == tmp_path / ".claude" / "explain-selection"
    assert settings.prompt_template == PLUGIN_ROOT / "templates" / "explain-prompt.txt"
    assert settings.fallback_cwd == tmp_path
    assert settings.max_chars == 200_000
    assert settings.long_selection is LongSelection.TRUNCATE
    assert settings.remember_target_minutes == 10


def test_derived_paths_hang_off_home(tmp_path: Path) -> None:
    settings = load_settings(_environ(tmp_path), PLUGIN_ROOT)
    assert settings.sessions_dir == settings.home / "sessions"
    assert settings.log_file == settings.home / "explain-selection.log"
    assert settings.last_target_file == settings.home / "last-target.json"
    assert settings.temp_dir == settings.home / "tmp"
    assert settings.remember_ttl_ms == 600_000


def test_environment_overrides_with_prefix(tmp_path: Path) -> None:
    environ = _environ(
        tmp_path,
        EXPLAIN_SELECTION_HOME=str(tmp_path / "elsewhere"),
        EXPLAIN_SELECTION_MAX_CHARS="500",
        EXPLAIN_SELECTION_LONG_SELECTION="tempfile",
        EXPLAIN_SELECTION_PROMPT_TEMPLATE="/etc/prompt.txt",
        EXPLAIN_SELECTION_REMEMBER_TARGET_MINUTES="3",
        EXPLAIN_SELECTION_FALLBACK_CWD="/work",
    )
    settings = load_settings(environ, PLUGIN_ROOT)
    assert settings.home == tmp_path / "elsewhere"
    assert settings.max_chars == 500
    assert settings.long_selection is LongSelection.TEMPFILE
    assert settings.prompt_template == Path("/etc/prompt.txt")
    assert settings.remember_target_minutes == 3
    assert settings.fallback_cwd == Path("/work")


def test_config_file_in_home_is_read(tmp_path: Path) -> None:
    home = tmp_path / ".claude" / "explain-selection"
    home.mkdir(parents=True)
    (home / "config.env").write_text(
        "EXPLAIN_SELECTION_MAX_CHARS=42\n"
        "EXPLAIN_SELECTION_PROMPT_TEMPLATE=/custom/prompt.txt\n"
        "UNRELATED=ignored\n"
        "EXPLAIN_SELECTION_UNKNOWN=ignored\n"
    )
    settings = load_settings(_environ(tmp_path), PLUGIN_ROOT)
    assert settings.max_chars == 42
    assert settings.prompt_template == Path("/custom/prompt.txt")


def test_environment_beats_config_file(tmp_path: Path) -> None:
    home = tmp_path / ".claude" / "explain-selection"
    home.mkdir(parents=True)
    (home / "config.env").write_text("EXPLAIN_SELECTION_MAX_CHARS=42\n")
    settings = load_settings(_environ(tmp_path, EXPLAIN_SELECTION_MAX_CHARS="7"), PLUGIN_ROOT)
    assert settings.max_chars == 7


def test_unprefixed_environment_keys_are_ignored(tmp_path: Path) -> None:
    settings = load_settings(_environ(tmp_path, MAX_CHARS="1"), PLUGIN_ROOT)
    assert settings.max_chars == 200_000


def test_invalid_values_fail_at_the_boundary(tmp_path: Path) -> None:
    environ = _environ(tmp_path, EXPLAIN_SELECTION_LONG_SELECTION="shout")
    with pytest.raises(ValidationError):
        load_settings(environ, PLUGIN_ROOT)


def test_settings_do_not_read_the_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXPLAIN_SELECTION_MAX_CHARS", "1")
    settings = load_settings(_environ(tmp_path), PLUGIN_ROOT)
    assert settings.max_chars == 200_000


def test_direct_construction_needs_only_the_context_fields() -> None:
    settings = Settings(home=Path("/h"), prompt_template=Path("/t"), fallback_cwd=Path("/c"))
    assert settings.max_chars == 200_000


def test_plugin_root_prefers_the_wrapper_export() -> None:
    environ = {"EXPLAIN_SELECTION_PLUGIN_ROOT": "/a", "CLAUDE_PLUGIN_ROOT": "/b"}
    assert resolve_plugin_root(environ, Path("/c")) == Path("/a")


def test_plugin_root_falls_back_to_claude_then_checkout() -> None:
    assert resolve_plugin_root({"CLAUDE_PLUGIN_ROOT": "/b"}, Path("/c")) == Path("/b")
    assert resolve_plugin_root({"CLAUDE_PLUGIN_ROOT": ""}, Path("/c")) == Path("/c")


def test_exported_plugin_root_is_none_unless_a_wrapper_or_claude_set_it() -> None:
    assert exported_plugin_root({}) is None
    assert exported_plugin_root({"CLAUDE_PLUGIN_ROOT": ""}) is None
    assert exported_plugin_root({"CLAUDE_PLUGIN_ROOT": "/b"}) == Path("/b")
    both = {"EXPLAIN_SELECTION_PLUGIN_ROOT": "/a", "CLAUDE_PLUGIN_ROOT": "/b"}
    assert exported_plugin_root(both) == Path("/a")
