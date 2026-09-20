"""Deep link construction for the mode A fallback."""

import pytest

from explain_selection.domain import (
    DEEP_LINK_QUERY_LIMIT,
    DEEP_LINK_TRUNCATION_MARKER,
    build_deep_link,
    fit_prompt_for_deep_link,
)


def test_link_encodes_cwd_and_prompt() -> None:
    url = build_deep_link("/Users/me/my proj", "explain: ls -la\nplease")
    assert url == "claude-cli://open?cwd=%2FUsers%2Fme%2Fmy%20proj&q=explain%3A%20ls%20-la%0Aplease"


def test_link_rejects_prompt_over_limit() -> None:
    with pytest.raises(ValueError, match="5000"):
        build_deep_link("/", "x" * (DEEP_LINK_QUERY_LIMIT + 1))


def test_fit_leaves_short_prompts_alone() -> None:
    assert fit_prompt_for_deep_link("short") == "short"


def test_fit_truncates_to_the_limit_with_a_marker() -> None:
    fitted = fit_prompt_for_deep_link("y" * 6000)
    assert len(fitted) == DEEP_LINK_QUERY_LIMIT
    assert fitted.endswith(DEEP_LINK_TRUNCATION_MARKER)
    assert build_deep_link("/", fitted).startswith("claude-cli://open?cwd=%2F&q=yyyy")
