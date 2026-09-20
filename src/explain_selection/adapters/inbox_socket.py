"""``InboxPoster`` over a Unix stream socket: connect, send both JSON lines, close.

The server sends no acknowledgement and keeps the connection open, so the client never waits
for a reply. The registry's recorded path is tried first, then the paths derived from the pid.
Connecting is behind a ``SocketConnector`` so the routing is unit-tested without a real socket.
"""

import socket
from collections.abc import Mapping
from typing import Protocol

from explain_selection.domain import candidate_socket_paths, encode_inbox_lines
from explain_selection.errors import InboxUnavailableError
from explain_selection.services import InboxAddress


class SocketConnector(Protocol):
    """Connects to one Unix socket, sends a payload, and closes."""

    def send(self, path: str, payload: bytes, *, timeout: float) -> None:
        """Deliver ``payload`` to the socket at ``path``; raise ``OSError`` on any failure."""
        ...


class UnixSocketConnector:
    """The real connector: a stdlib ``AF_UNIX`` stream socket."""

    def send(self, path: str, payload: bytes, *, timeout: float) -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(path)
            sock.sendall(payload)


class InboxSocketPoster:
    """Posts a message into a session's inbox, trying each candidate socket path in turn."""

    def __init__(
        self,
        connector: SocketConnector,
        env: Mapping[str, str],
        uid: int,
        *,
        timeout_s: float = 2.0,
    ) -> None:
        self._connector = connector
        self._env = env
        self._uid = uid
        self._timeout_s = timeout_s

    def post(self, address: InboxAddress, content: str) -> None:
        payload = encode_inbox_lines(address.token, content)
        last_error: OSError | None = None
        for path in self._paths(address):
            try:
                self._connector.send(path, payload, timeout=self._timeout_s)
                return
            except OSError as exc:
                last_error = exc
        raise InboxUnavailableError(
            f"no inbox socket accepted the message for pid {address.pid}"
        ) from last_error

    def _paths(self, address: InboxAddress) -> list[str]:
        ordered: list[str] = []
        if address.socket_path:
            ordered.append(address.socket_path)
        for candidate in candidate_socket_paths(address.pid, self._env, self._uid):
            if candidate not in ordered:
                ordered.append(candidate)
        return ordered


__all__ = ["InboxSocketPoster", "SocketConnector", "UnixSocketConnector"]
