"""Parse the JSON a hook receives on stdin into a typed, tolerant model.

Hooks must never break a session, so malformed or empty input yields an all-``None`` model
rather than an error; the important routing values (socket, token) come from the environment,
not from this JSON.
"""

import logging

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class HookStdin(BaseModel):
    """The subset of hook stdin fields this plugin reads; unknown keys ignored."""

    model_config = ConfigDict(extra="ignore")

    session_id: str | None = None
    cwd: str | None = None
    hook_event_name: str | None = None


def parse_hook_stdin(raw: str) -> HookStdin:
    """Return the parsed stdin, or an empty model when it is blank or malformed."""
    if not raw.strip():
        return HookStdin()
    try:
        return HookStdin.model_validate_json(raw)
    except ValidationError:
        logger.warning("ignoring unparseable hook stdin")
        return HookStdin()


__all__ = ["HookStdin", "parse_hook_stdin"]
