"""JsonClaudeSettingsReader: the two Claude Code settings the doctor looks at.

``crossSessionInbound`` decides whether inbound messages are accepted, held or refused;
``enabledPlugins`` tells whether this plugin's hooks run at all. Both live in the user,
project and local ``settings.json`` files; later files override earlier ones.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from explain_selection.domain import InboundPolicy
from explain_selection.services import ClaudeSettingsFacts

logger = logging.getLogger(__name__)


class _SettingsModel(BaseModel):
    """The subset of a Claude Code ``settings.json`` the doctor reads; other keys are ignored."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    cross_session_inbound: InboundPolicy | None = Field(default=None, alias="crossSessionInbound")
    enabled_plugins: dict[str, bool] = Field(
        default_factory=dict[str, bool], alias="enabledPlugins"
    )


@dataclass(frozen=True, slots=True)
class JsonClaudeSettingsReader:
    """Merges ``paths`` in order; a missing file is skipped, an invalid one logged and skipped."""

    paths: tuple[Path, ...]
    plugin_name: str

    def read(self) -> ClaudeSettingsFacts:
        policy: InboundPolicy | None = None
        enabled = False
        prefix = f"{self.plugin_name}@"
        for path in self.paths:
            model = _load(path)
            if model is None:
                continue
            if model.cross_session_inbound is not None:
                policy = model.cross_session_inbound
            if any(key.startswith(prefix) and on for key, on in model.enabled_plugins.items()):
                enabled = True
        return ClaudeSettingsFacts(cross_session_inbound=policy, plugin_enabled=enabled)


def _load(path: Path) -> _SettingsModel | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("could not read %s: %s", path, type(exc).__name__)
        return None
    try:
        return _SettingsModel.model_validate_json(raw)
    except ValidationError:
        logger.warning("skipping unreadable settings file %s", path)
        return None


__all__ = ["JsonClaudeSettingsReader"]
