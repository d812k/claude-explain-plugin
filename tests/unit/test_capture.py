"""The capture entrypoint routes argv and stdin into delivery and reports by notification."""

from pathlib import Path

from explain_selection.domain import Pid, SessionStatus
from explain_selection.entrypoints.capture import (
    BadUsage,
    FromArgument,
    FromStdin,
    build_policy,
    parse_argv,
    run,
)
from explain_selection.entrypoints.settings import Settings
from explain_selection.services import DeliverDeps, DeliveryPolicy, LongSelection
from tests.builders import entry, session
from tests.fakes import (
    FakeChooser,
    FakeClock,
    FakeFocus,
    FakeMemory,
    FakeNotifier,
    FakeOpener,
    FakePoster,
    FakeRegistry,
    FakeSessions,
    FakeTempFiles,
)

POLICY = DeliveryPolicy(
    max_chars=1_000,
    prompt_template="Explain: {text}",
    remember_ttl_ms=600_000,
    long_selection=LongSelection.TRUNCATE,
    fallback_cwd="/home/user",
)


def _deps(
    *,
    status: SessionStatus = SessionStatus.IDLE,
    poster: FakePoster | None = None,
    live: bool = True,
) -> tuple[DeliverDeps, FakePoster, FakeOpener]:
    poster = poster if poster is not None else FakePoster()
    opener = FakeOpener()
    sessions = (session(4242, status=status),) if live else ()
    entries = {Pid(4242): entry(4242)} if live else {}
    deps = DeliverDeps(
        clock=FakeClock(),
        sessions=FakeSessions(sessions),
        registry=FakeRegistry(entries=entries),
        focus=FakeFocus(),
        memory=FakeMemory(),
        poster=poster,
        chooser=FakeChooser(),
        opener=opener,
        tempfiles=FakeTempFiles(),
    )
    return deps, poster, opener


def _no_stdin() -> str:
    raise AssertionError("stdin must not be read")


def test_argv_forms() -> None:
    assert parse_argv([]) == FromStdin()
    assert parse_argv(["--text", "-"]) == FromStdin()
    assert parse_argv(["--text", "hello"]) == FromArgument("hello")
    assert isinstance(parse_argv(["--bogus"]), BadUsage)
    assert isinstance(parse_argv(["--text"]), BadUsage)


def test_stdin_selection_is_injected_into_the_idle_session() -> None:
    deps, poster, _ = _deps()
    notifier = FakeNotifier()
    assert run([], lambda: "ls -la\n", POLICY, deps, notifier) == 0
    (address, content), *rest = poster.posts
    assert rest == []
    assert address.pid == Pid(4242)
    assert content == "Explain: ls -la"
    assert notifier.shown == []


def test_text_argument_is_used_without_reading_stdin() -> None:
    deps, poster, _ = _deps()
    assert run(["--text", "grep -r"], _no_stdin, POLICY, deps, FakeNotifier()) == 0
    assert poster.posts[0][1] == "Explain: grep -r"


def test_dash_reads_stdin() -> None:
    deps, poster, _ = _deps()
    assert run(["--text", "-"], lambda: "from stdin", POLICY, deps, FakeNotifier()) == 0
    assert poster.posts[0][1] == "Explain: from stdin"


def test_busy_session_still_receives_and_the_user_is_told() -> None:
    deps, poster, _ = _deps(status=SessionStatus.BUSY)
    notifier = FakeNotifier()
    assert run([], lambda: "text", POLICY, deps, notifier) == 0
    assert len(poster.posts) == 1
    assert notifier.shown == [
        (
            "Explain selection",
            "Sent to work - /work (busy); it is busy and will answer when it is free.",
        )
    ]


def test_truncated_selection_is_injected_and_the_user_is_told() -> None:
    deps, poster, _ = _deps()
    notifier = FakeNotifier()
    assert run([], lambda: "x" * 1_500, POLICY, deps, notifier) == 0
    assert len(poster.posts) == 1
    assert notifier.shown == [
        ("Explain selection", "Selection truncated to 1000 characters (1500 selected).")
    ]


def test_busy_and_truncated_are_both_reported() -> None:
    deps, _, _ = _deps(status=SessionStatus.WAITING)
    notifier = FakeNotifier()
    assert run([], lambda: "x" * 1_001, POLICY, deps, notifier) == 0
    messages = [message for _, message in notifier.shown]
    assert messages == [
        "Sent to work - /work (waiting); it is waiting and will answer when it is free.",
        "Selection truncated to 1000 characters (1001 selected).",
    ]


def test_truncated_selection_into_a_new_window_is_reported() -> None:
    deps, _, opener = _deps(live=False)
    notifier = FakeNotifier()
    assert run([], lambda: "x" * 1_500, POLICY, deps, notifier) == 0
    assert len(opener.opened) == 1
    assert notifier.shown == [
        ("Explain selection", "Selection truncated to 1000 characters (1500 selected).")
    ]


def test_no_live_session_opens_a_new_window_quietly() -> None:
    deps, _, opener = _deps(live=False)
    notifier = FakeNotifier()
    assert run([], lambda: "text", POLICY, deps, notifier) == 0
    assert len(opener.opened) == 1
    assert notifier.shown == []


def test_empty_selection_is_reported() -> None:
    deps, poster, _ = _deps()
    notifier = FakeNotifier()
    assert run([], lambda: "   \n", POLICY, deps, notifier) == 0
    assert poster.posts == []
    assert notifier.shown == [("Explain selection", "Nothing selected.")]


def test_delivery_failure_is_notified_and_exits_zero() -> None:
    deps, _, _ = _deps(poster=FakePoster(fail=True))
    notifier = FakeNotifier()
    assert run([], lambda: "text", POLICY, deps, notifier) == 0
    assert notifier.shown == [
        ("Explain selection", "Could not deliver the selection; see the log.")
    ]


def test_bad_usage_is_notified_and_exits_zero() -> None:
    deps, poster, _ = _deps()
    notifier = FakeNotifier()
    assert run(["--nope"], _no_stdin, POLICY, deps, notifier) == 0
    assert poster.posts == []
    assert notifier.shown[0][1].startswith("usage: explain-selection-capture")


def test_failing_notifier_never_raises() -> None:
    deps, _, _ = _deps(poster=FakePoster(fail=True))
    assert run([], lambda: "text", POLICY, deps, FakeNotifier(fail=True)) == 0


def test_policy_reads_the_template_file(tmp_path: Path) -> None:
    template = tmp_path / "prompt.txt"
    template.write_text("Say: {text}", encoding="utf-8")
    settings = Settings(
        home=tmp_path,
        prompt_template=template,
        fallback_cwd=tmp_path / "cwd",
        max_chars=99,
        long_selection=LongSelection.TEMPFILE,
        remember_target_minutes=2,
    )
    policy = build_policy(settings)
    assert policy == DeliveryPolicy(
        max_chars=99,
        prompt_template="Say: {text}",
        remember_ttl_ms=120_000,
        long_selection=LongSelection.TEMPFILE,
        fallback_cwd=str(tmp_path / "cwd"),
    )
