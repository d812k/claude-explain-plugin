"""OpenLinkOpener hands a URL to the macOS open command."""

import pytest

from explain_selection.adapters import CommandResult, OpenLinkOpener
from explain_selection.errors import SubprocessError
from tests.fakes import FakeRunner

URL = "claude-cli://open?cwd=%2Fwork&q=hi"


def test_opens_the_url() -> None:
    runner = FakeRunner()
    OpenLinkOpener(runner).open(URL)
    assert runner.calls == [("open", URL)]


def test_non_zero_exit_raises() -> None:
    runner = FakeRunner(queue=[CommandResult(returncode=1, stdout="", stderr="no handler")])
    with pytest.raises(SubprocessError):
        OpenLinkOpener(runner).open(URL)
