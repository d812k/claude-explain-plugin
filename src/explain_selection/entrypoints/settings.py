"""Runtime configuration: one pydantic-settings object built once per process.

Precedence, highest first: process environment (``EXPLAIN_SELECTION_*``), then
``<home>/config.env`` with the same prefix, then defaults. Two defaults depend on the
process context and are resolved in :func:`load_settings`: the prompt template lives
under the plugin root, and ``home`` and ``fallback_cwd`` derive from ``$HOME``. Nothing
in this module reads ``os.environ``; the caller passes an explicit mapping.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from explain_selection.services import LongSelection

ENV_PREFIX: Final[str] = "EXPLAIN_SELECTION_"
CONFIG_FILE_NAME: Final[str] = "config.env"
PLUGIN_ROOT_VAR: Final[str] = "EXPLAIN_SELECTION_PLUGIN_ROOT"
_TEMPLATE_RELATIVE: Final[Path] = Path("templates") / "explain-prompt.txt"
_HOME_RELATIVE: Final[Path] = Path(".claude") / "explain-selection"
_MS_PER_MINUTE: Final[int] = 60_000


class Settings(BaseSettings):
    """All configuration the entrypoints need; derived paths hang off ``home``."""

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, extra="ignore", frozen=True)

    home: Path
    max_chars: int = 200_000
    long_selection: LongSelection = LongSelection.TRUNCATE
    prompt_template: Path
    remember_target_minutes: int = 10
    fallback_cwd: Path

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Only explicit constructor values count; :func:`load_settings` merges the rest."""
        return (init_settings,)

    @property
    def sessions_dir(self) -> Path:
        """Registry directory: one ``<pid>.json`` per live session."""
        return self.home / "sessions"

    @property
    def log_file(self) -> Path:
        """Diagnostics for hooks and the hotkey; never contains tokens."""
        return self.home / "explain-selection.log"

    @property
    def last_target_file(self) -> Path:
        """Where the user's last manual pick is remembered."""
        return self.home / "last-target.json"

    @property
    def temp_dir(self) -> Path:
        """Long selections for mode A are written here."""
        return self.home / "tmp"

    @property
    def remember_ttl_ms(self) -> int:
        """``remember_target_minutes`` in milliseconds, as the delivery policy wants it."""
        return self.remember_target_minutes * _MS_PER_MINUTE


def exported_plugin_root(environ: Mapping[str, str]) -> Path | None:
    """The plugin checkout the wrapper or Claude Code exported, or ``None`` when neither did."""
    for key in (PLUGIN_ROOT_VAR, "CLAUDE_PLUGIN_ROOT"):
        value = environ.get(key)
        if value:
            return Path(value)
    return None


def resolve_plugin_root(environ: Mapping[str, str], fallback: Path) -> Path:
    """The plugin checkout: from the wrapper's export, else Claude Code's, else ``fallback``."""
    exported = exported_plugin_root(environ)
    return fallback if exported is None else exported


def load_settings(environ: Mapping[str, str], plugin_root: Path) -> Settings:
    """Build Settings from ``environ``, ``<home>/config.env`` and context-dependent defaults."""
    user_home = Path(environ.get("HOME") or "/")
    overrides = _prefixed_values(environ)
    home = Path(overrides.get("home") or user_home / _HOME_RELATIVE)
    defaults: dict[str, object] = {
        "home": home,
        "prompt_template": plugin_root / _TEMPLATE_RELATIVE,
        "fallback_cwd": user_home,
    }
    merged: dict[str, object] = {
        **defaults,
        **_config_file_values(home / CONFIG_FILE_NAME),
        **overrides,
    }
    return Settings.model_validate(merged)


def _prefixed_values(environ: Mapping[str, str]) -> dict[str, str]:
    """``EXPLAIN_SELECTION_MAX_CHARS=1`` becomes ``{"max_chars": "1"}``; unknown keys dropped."""
    values: dict[str, str] = {}
    for key, value in environ.items():
        if key.startswith(ENV_PREFIX):
            field_name = key[len(ENV_PREFIX) :].lower()
            if field_name in Settings.model_fields:
                values[field_name] = value
    return values


def _config_file_values(path: Path) -> dict[str, object]:
    """Known-field values from ``config.env`` when it exists, else nothing."""
    if not path.is_file():
        return {}
    raw = DotEnvSettingsSource(Settings, env_file=path)()
    return {name: value for name, value in raw.items() if name in Settings.model_fields}


__all__ = [
    "CONFIG_FILE_NAME",
    "ENV_PREFIX",
    "PLUGIN_ROOT_VAR",
    "Settings",
    "exported_plugin_root",
    "load_settings",
    "resolve_plugin_root",
]
