"""JsonClaudeSettingsReader merges settings files in order; exercised only under tmp_path."""

import logging
from pathlib import Path

import pytest

from explain_selection.adapters import JsonClaudeSettingsReader
from explain_selection.services import ClaudeSettingsFacts

PLUGIN = "explain-selection"


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / "user" / "settings.json",
        tmp_path / "project" / "settings.json",
        tmp_path / "project" / "settings.local.json",
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_no_files_means_the_default_policy_and_a_disabled_plugin(tmp_path: Path) -> None:
    facts = JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read()
    assert facts == ClaudeSettingsFacts(cross_session_inbound=None, plugin_enabled=False)


def test_the_user_file_sets_the_policy_and_enables_the_plugin(tmp_path: Path) -> None:
    user, _, _ = _paths(tmp_path)
    _write(
        user,
        '{"crossSessionInbound": "accept", "theme": "dark", '
        '"enabledPlugins": {"explain-selection@local": true, "other@m": true}}',
    )
    facts = JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read()
    assert facts == ClaudeSettingsFacts(cross_session_inbound="accept", plugin_enabled=True)


def test_a_later_file_overrides_the_policy_and_any_file_can_enable_the_plugin(
    tmp_path: Path,
) -> None:
    user, project, local = _paths(tmp_path)
    _write(user, '{"crossSessionInbound": "accept"}')
    _write(project, '{"crossSessionInbound": "refuse"}')
    _write(local, '{"enabledPlugins": {"explain-selection@dev": true}}')
    facts = JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read()
    assert facts == ClaudeSettingsFacts(cross_session_inbound="refuse", plugin_enabled=True)


def test_a_disabled_entry_or_another_plugin_does_not_count(tmp_path: Path) -> None:
    user, _, _ = _paths(tmp_path)
    _write(
        user, '{"enabledPlugins": {"explain-selection@local": false, "explain-other@local": true}}'
    )
    assert not JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read().plugin_enabled


def test_an_invalid_file_is_logged_and_skipped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    user, project, _ = _paths(tmp_path)
    _write(user, '{"crossSessionInbound": "hold"}')
    _write(project, "{not json")
    with caplog.at_level(logging.WARNING):
        facts = JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read()
    assert facts.cross_session_inbound == "hold"
    assert any("settings.json" in record.getMessage() for record in caplog.records)


def test_an_unknown_policy_value_invalidates_only_that_file(tmp_path: Path) -> None:
    user, project, _ = _paths(tmp_path)
    _write(user, '{"crossSessionInbound": "accept"}')
    _write(project, '{"crossSessionInbound": "maybe"}')
    assert JsonClaudeSettingsReader(_paths(tmp_path), PLUGIN).read().cross_session_inbound == (
        "accept"
    )
