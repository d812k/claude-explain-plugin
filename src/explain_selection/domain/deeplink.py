"""Pure construction of the ``claude-cli://open`` deep link used by mode A."""

from typing import Final
from urllib.parse import quote

DEEP_LINK_QUERY_LIMIT: Final[int] = 5_000
DEEP_LINK_TRUNCATION_MARKER: Final[str] = " ...[truncated]"
_SCHEME: Final[str] = "claude-cli://open"


def fit_prompt_for_deep_link(prompt: str, limit: int = DEEP_LINK_QUERY_LIMIT) -> str:
    """Shorten ``prompt`` so it fits the deep link's query limit, marking any cut."""
    if len(prompt) <= limit:
        return prompt
    keep = max(limit - len(DEEP_LINK_TRUNCATION_MARKER), 0)
    return prompt[:keep].rstrip() + DEEP_LINK_TRUNCATION_MARKER


def build_deep_link(cwd: str, prompt: str) -> str:
    """Return the URL that opens a new Claude Code window in ``cwd`` with ``prompt`` filled in."""
    if len(prompt) > DEEP_LINK_QUERY_LIMIT:
        msg = f"deep link prompt exceeds {DEEP_LINK_QUERY_LIMIT} characters"
        raise ValueError(msg)
    return f"{_SCHEME}?cwd={quote(cwd, safe='')}&q={quote(prompt, safe='')}"


__all__ = [
    "DEEP_LINK_QUERY_LIMIT",
    "DEEP_LINK_TRUNCATION_MARKER",
    "build_deep_link",
    "fit_prompt_for_deep_link",
]
