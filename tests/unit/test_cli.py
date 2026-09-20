"""The explain-selection command line: version, sessions and send, driven through ``run``."""

import io
from collections.abc import Sequence

import pytest

from explain_selection.domain import Pid, SessionStatus
from explain_selection.entrypoints.cli import package_version, run
from explain_selection.services import SendDeps
from tests.builders import entry, session
from tests.fakes import FakePoster, FakeProbe, FakeRegistry, FakeSessions


def _deps(*, poster: FakePoster | None = None, sessions: FakeSessions | None = None) -> SendDeps:
    live = (session(10, name="alpha", status=SessionStatus.BUSY), session(20, cwd="/home/me/proj"))
    return SendDeps(
        sessions=sessions if sessions is not None else FakeSessions(live),
        registry=FakeRegistry(entries={Pid(10): entry(10)}),
        poster=poster if poster is not None else FakePoster(),
        probe=FakeProbe(),
    )


def _no_stdin() -> str:
    raise AssertionError("stdin must not be read")


def _run(argv: Sequence[str], deps: SendDeps, stdin: str | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    stdin_text = _no_stdin if stdin is None else (lambda: stdin)
    code = run(argv, stdin_text, deps, out, err)
    return code, out.getvalue(), err.getvalue()


def test_version_prints_the_package_version() -> None:
    code, out, err = _run(["version"], _deps())
    assert (code, out, err) == (0, f"{package_version()}\n", "")


def test_version_is_a_dotted_number_when_installed() -> None:
    assert package_version().count(".") >= 2


def test_a_subcommand_is_required() -> None:
    with pytest.raises(SystemExit):
        _run([], _deps())


def test_sessions_prints_one_aligned_line_per_live_session_in_chooser_order() -> None:
    code, out, err = _run(["sessions"], _deps())
    assert code == 0
    assert err == ""
    assert out.splitlines() == [
        "20  idle  unregistered  proj   /home/me/proj",
        "10  busy  registered    alpha  /work",
    ]


def test_sessions_with_no_live_session_says_so_on_stderr() -> None:
    code, out, err = _run(["sessions"], _deps(sessions=FakeSessions()))
    assert (code, out) == (0, "")
    assert err == "No live Claude Code sessions.\n"


def test_send_posts_the_text_argument_verbatim_and_confirms() -> None:
    poster = FakePoster()
    code, out, err = _run(["send", "--pid", "10", "--text", "hello {x}\n"], _deps(poster=poster))
    assert (code, err) == (0, "")
    assert poster.posts == [(poster.posts[0][0], "hello {x}\n")]
    assert poster.posts[0][0].pid == Pid(10)
    assert poster.posts[0][0].token == entry(10).token
    assert out == "Sent 10 characters to alpha - /work (busy).\n"


def test_send_reads_stdin_when_text_is_a_dash() -> None:
    poster = FakePoster()
    code, _, _ = _run(
        ["send", "--pid", "20", "--text", "-"], _deps(poster=poster), stdin="from stdin"
    )
    assert code == 0
    assert poster.posts[0][1] == "from stdin"
    assert poster.posts[0][0].token is None


def test_send_reads_stdin_when_text_is_absent() -> None:
    poster = FakePoster()
    code, _, _ = _run(["send", "--pid", "20"], _deps(poster=poster), stdin="piped")
    assert code == 0
    assert poster.posts[0][1] == "piped"


def test_send_with_blank_text_is_a_usage_error_and_posts_nothing() -> None:
    poster = FakePoster()
    code, out, err = _run(["send", "--pid", "10"], _deps(poster=poster), stdin="  \n")
    assert (code, out) == (2, "")
    assert err.startswith("usage: explain-selection send")
    assert poster.posts == []


def test_send_to_an_unknown_pid_fails_with_the_reason_on_stderr() -> None:
    poster = FakePoster()
    code, out, err = _run(["send", "--pid", "999", "--text", "x"], _deps(poster=poster))
    assert (code, out) == (1, "")
    assert "no live interactive session with pid 999" in err
    assert poster.posts == []


def test_send_to_a_dead_socket_fails_with_the_reason_on_stderr() -> None:
    code, out, err = _run(
        ["send", "--pid", "10", "--text", "x"], _deps(poster=FakePoster(fail=True))
    )
    assert (code, out) == (1, "")
    assert "no socket for pid 10" in err


def test_send_requires_a_pid() -> None:
    with pytest.raises(SystemExit):
        _run(["send", "--text", "x"], _deps())


def test_a_failing_session_query_is_reported_and_exits_one() -> None:
    code, out, err = _run(["sessions"], _deps(sessions=FakeSessions(fail=True)))
    assert (code, out) == (1, "")
    assert "claude agents failed" in err
