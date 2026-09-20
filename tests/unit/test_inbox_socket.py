"""InboxSocketPoster tries each candidate path and reports when none accept the message."""

import pytest

from explain_selection.adapters import InboxSocketPoster
from explain_selection.domain import InboxToken, Pid, encode_inbox_lines
from explain_selection.errors import InboxUnavailableError
from explain_selection.services import InboxAddress
from tests.fakes import FakeConnector

ENV = {"XDG_RUNTIME_DIR": "/run/user/501"}
PRIMARY = "/run/user/501/cc-socks/2268544.sock"
FALLBACK = "/tmp/cc-socks-501/2268544.sock"
LEGACY = "/custom/legacy.sock"


def _poster(connector: FakeConnector) -> InboxSocketPoster:
    return InboxSocketPoster(connector, env=ENV, uid=501)


def test_posts_to_the_registry_path_first() -> None:
    connector = FakeConnector()
    address = InboxAddress(pid=Pid(2268544), socket_path=LEGACY, token=InboxToken("tok"))
    _poster(connector).post(address, "hello")
    assert connector.sent[0][0] == LEGACY
    assert connector.sent[0][1] == encode_inbox_lines(InboxToken("tok"), "hello")


def test_falls_back_when_the_first_path_refuses() -> None:
    connector = FakeConnector(fail_paths={LEGACY})
    address = InboxAddress(pid=Pid(2268544), socket_path=LEGACY, token=None)
    _poster(connector).post(address, "hi")
    assert connector.sent[0][0] == PRIMARY


def test_derives_candidate_paths_when_registry_path_is_absent() -> None:
    connector = FakeConnector()
    address = InboxAddress(pid=Pid(2268544), socket_path=None, token=None)
    _poster(connector).post(address, "hi")
    assert connector.sent[0][0] == PRIMARY


def test_all_paths_failing_raises_inbox_unavailable() -> None:
    connector = FakeConnector(fail_paths={LEGACY, PRIMARY, FALLBACK})
    address = InboxAddress(pid=Pid(2268544), socket_path=LEGACY, token=None)
    with pytest.raises(InboxUnavailableError):
        _poster(connector).post(address, "hi")
