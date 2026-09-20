"""InboxSocketPoster against a real AF_UNIX server. Runs only under make test-all."""

import socket
import threading
from pathlib import Path

import pytest

from explain_selection.adapters import InboxSocketPoster, UnixSocketConnector
from explain_selection.domain import InboxToken, Pid, encode_inbox_lines
from explain_selection.services import InboxAddress


@pytest.mark.integration
def test_a_real_socket_receives_both_wire_lines(tmp_path: Path) -> None:
    sock_path = str(tmp_path / "s.sock")
    received = bytearray()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)

    def serve() -> None:
        conn, _ = server.accept()
        with conn:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)

    worker = threading.Thread(target=serve)
    worker.start()
    try:
        poster = InboxSocketPoster(UnixSocketConnector(), env={}, uid=0)
        address = InboxAddress(pid=Pid(1), socket_path=sock_path, token=InboxToken("tok"))
        poster.post(address, "explain this")
        worker.join(timeout=5)
    finally:
        server.close()

    assert bytes(received) == encode_inbox_lines(InboxToken("tok"), "explain this")
