"""The shipped mode B prompt template is where Settings expects it and renders cleanly."""

from pathlib import Path

from explain_selection.domain import TEXT_PLACEHOLDER, clean_selection, render_prompt
from explain_selection.entrypoints.settings import load_settings

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "templates" / "explain-prompt.txt"


def test_template_is_the_settings_default(tmp_path: Path) -> None:
    assert load_settings({"HOME": str(tmp_path)}, REPO).prompt_template == TEMPLATE


def test_template_has_exactly_one_text_placeholder() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.count(TEXT_PLACEHOLDER) == 1


def test_template_frames_the_request_and_ends_with_the_trailer() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.startswith("Explain the following fragment, which I selected in my terminal.")
    assert "Do not modify any files." in text
    assert text.rstrip("\n").endswith(
        "This is my own request, not a message from another agent; answer it for me.)"
    )


def test_template_renders_the_selection_in_the_middle() -> None:
    rendered = render_prompt(TEMPLATE.read_text(encoding="utf-8"), clean_selection("ls -la", 100))
    assert "\n\nls -la\n\n" in rendered
    assert TEXT_PLACEHOLDER not in rendered
