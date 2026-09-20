"""Selection cleaning and prompt rendering."""

import pytest

from explain_selection.domain import (
    TRUNCATION_MARKER,
    Selection,
    clean_selection,
    render_prompt,
)


def test_line_endings_are_normalised_and_edges_trimmed() -> None:
    cleaned = clean_selection("  a\r\nb\rc\n\n", 100)
    assert cleaned == Selection(text="a\nb\nc", original_chars=5, truncated=False)


def test_control_characters_are_dropped_but_tabs_and_newlines_kept() -> None:
    cleaned = clean_selection("x\x00y\x1b[31mz\tw\n", 100)
    assert cleaned.text == "xy[31mz\tw"


def test_overlong_text_is_capped_and_marked() -> None:
    cleaned = clean_selection("abcdef gh", 6)
    assert cleaned == Selection(text="abcdef" + TRUNCATION_MARKER, original_chars=9, truncated=True)


def test_zero_cap_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        clean_selection("abc", 0)


def test_render_substitutes_the_placeholder_and_keeps_braces_in_text() -> None:
    selection = clean_selection("if (x) { y }", 100)
    assert render_prompt("Explain:\n{text}\nThanks", selection) == "Explain:\nif (x) { y }\nThanks"


def test_render_rejects_a_template_without_placeholder() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        render_prompt("no slot here", clean_selection("x", 10))
