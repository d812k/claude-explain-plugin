"""Property tests: cleaning is bounded and idempotent; rendering preserves the text."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from explain_selection.domain import (
    TRUNCATION_MARKER,
    build_deep_link,
    clean_selection,
    encode_inbox_lines,
    fit_prompt_for_deep_link,
    render_prompt,
)

texts = st.text(max_size=400)
caps = st.integers(min_value=1, max_value=300)


@pytest.mark.prop
@given(raw=texts, cap=caps)
def test_cleaned_text_respects_the_cap_plus_marker(raw: str, cap: int) -> None:
    cleaned = clean_selection(raw, cap)
    limit = cap + len(TRUNCATION_MARKER) if cleaned.truncated else cap
    assert len(cleaned.text) <= limit
    assert cleaned.truncated == (cleaned.original_chars > cap)


@pytest.mark.prop
@given(raw=texts)
def test_cleaning_is_idempotent_when_nothing_is_cut(raw: str) -> None:
    once = clean_selection(raw, 10_000)
    twice = clean_selection(once.text, 10_000)
    assert twice.text == once.text


@pytest.mark.prop
@given(raw=texts)
def test_rendered_prompt_contains_the_cleaned_text_verbatim(raw: str) -> None:
    cleaned = clean_selection(raw, 10_000)
    assert cleaned.text in render_prompt("before\n{text}\nafter", cleaned)


@pytest.mark.prop
@given(prompt=st.text(max_size=6_000))
def test_fitted_prompts_always_build_a_link(prompt: str) -> None:
    assert build_deep_link("/tmp", fit_prompt_for_deep_link(prompt)).startswith("claude-cli://")


@pytest.mark.prop
@given(content=texts)
def test_wire_payload_is_exactly_one_line_per_message(content: str) -> None:
    assert encode_inbox_lines(None, content).count(b"\n") == 1
