"""parse_hook_stdin reads the hook JSON tolerantly, never raising."""

from explain_selection.adapters import parse_hook_stdin


def test_parses_known_fields_and_ignores_the_rest() -> None:
    parsed = parse_hook_stdin(
        '{"session_id": "abc", "cwd": "/work", "hook_event_name": "SessionStart", "extra": 1}'
    )
    assert parsed.session_id == "abc"
    assert parsed.cwd == "/work"
    assert parsed.hook_event_name == "SessionStart"


def test_blank_input_is_an_empty_model() -> None:
    parsed = parse_hook_stdin("   \n  ")
    assert parsed.session_id is None
    assert parsed.cwd is None


def test_malformed_input_is_an_empty_model() -> None:
    assert parse_hook_stdin("{not json").session_id is None
