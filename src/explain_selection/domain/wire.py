"""Pure encoding of the inbox socket protocol: one JSON object per line."""

import json

from explain_selection.domain.models import InboxToken


def encode_inbox_lines(token: InboxToken | None, content: str) -> bytes:
    """Encode the optional auth line followed by the user message line."""
    lines: list[str] = []
    if token is not None:
        lines.append(json.dumps({"type": "auth", "token": token}, ensure_ascii=False))
    message = {"type": "user", "message": {"role": "user", "content": content}}
    lines.append(json.dumps(message, ensure_ascii=False))
    return ("\n".join(lines) + "\n").encode()


__all__ = ["encode_inbox_lines"]
