"""Wire encoding matches the inbox socket protocol verified in Phase 0."""

import json

from explain_selection.domain import InboxToken, encode_inbox_lines


def test_auth_line_precedes_user_line_and_each_ends_with_newline() -> None:
    payload = encode_inbox_lines(InboxToken("t0k"), "explain: x")
    lines = payload.decode().split("\n")
    assert lines[-1] == ""
    assert json.loads(lines[0]) == {"type": "auth", "token": "t0k"}
    assert json.loads(lines[1]) == {
        "type": "user",
        "message": {"role": "user", "content": "explain: x"},
    }
    assert len(lines) == 3


def test_without_token_only_the_user_line_is_sent() -> None:
    payload = encode_inbox_lines(None, "hi")
    lines = payload.decode().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["type"] == "user"


def test_newlines_inside_content_never_break_the_line_framing() -> None:
    payload = encode_inbox_lines(None, "line one\nline two\n")
    assert payload.count(b"\n") == 1
    assert json.loads(payload.decode())["message"]["content"] == "line one\nline two\n"
