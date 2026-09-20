"""Pure cleaning and capping of the captured selection, and prompt rendering."""

import re
from dataclasses import dataclass
from typing import Final

TEXT_PLACEHOLDER: Final[str] = "{text}"
TRUNCATION_MARKER: Final[str] = "\n[... truncated by explain-selection ...]"

_CONTROL_CHARS: Final[re.Pattern[str]] = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class Selection:
    """The selection after cleaning, ready to be placed into a prompt."""

    text: str
    original_chars: int
    truncated: bool


def clean_selection(raw: str, max_chars: int) -> Selection:
    """Normalise line endings, drop control characters, trim, and cap at ``max_chars``."""
    if max_chars <= 0:
        msg = "max_chars must be positive"
        raise ValueError(msg)
    text = _CONTROL_CHARS.sub("", raw.replace("\r\n", "\n").replace("\r", "\n")).strip()
    original = len(text)
    if original > max_chars:
        return Selection(text[:max_chars].rstrip() + TRUNCATION_MARKER, original, True)
    return Selection(text, original, False)


def render_prompt(template: str, selection: Selection) -> str:
    """Substitute the selection into the template; braces in the text are left alone."""
    if TEXT_PLACEHOLDER not in template:
        msg = f"prompt template lacks the {TEXT_PLACEHOLDER} placeholder"
        raise ValueError(msg)
    return template.replace(TEXT_PLACEHOLDER, selection.text)


__all__ = [
    "TEXT_PLACEHOLDER",
    "TRUNCATION_MARKER",
    "Selection",
    "clean_selection",
    "render_prompt",
]
