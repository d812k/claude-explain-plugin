"""The deliver use case routes a selection to mode B, mode A, or the chooser."""

from dataclasses import replace

import pytest

from explain_selection.adapters import CommandResult, OsascriptFocus
from explain_selection.domain import (
    Focus,
    LiveSession,
    PickReason,
    Pid,
    RememberedTarget,
    clean_selection,
    join_targets,
)
from explain_selection.services import (
    MODE_A_SKILL,
    Cancelled,
    DeliverDeps,
    DeliveryPolicy,
    Injected,
    LongSelection,
    NothingToSend,
    OpenedNewWindow,
    deliver_selection,
)
from tests.builders import entry, session
from tests.fakes import (
    FakeChooser,
    FakeClock,
    FakeFocus,
    FakeMemory,
    FakeOpener,
    FakePoster,
    FakeProbe,
    FakeRegistry,
    FakeRunner,
    FakeSessions,
    FakeTempFiles,
)

TEMPLATE = "Explain this:\n{text}\n(my own request)"
NOW = 1_700_000_600_000


def _policy(
    *,
    max_chars: int = 10_000,
    long_selection: LongSelection = LongSelection.TRUNCATE,
) -> DeliveryPolicy:
    return DeliveryPolicy(
        max_chars=max_chars,
        prompt_template=TEMPLATE,
        remember_ttl_ms=600_000,
        long_selection=long_selection,
        fallback_cwd="/home/me",
    )


def _deps() -> DeliverDeps:
    """All-default deps; tests override individual fakes with dataclasses.replace."""
    return DeliverDeps(
        clock=FakeClock(now=NOW),
        sessions=FakeSessions(),
        registry=FakeRegistry(),
        focus=FakeFocus(),
        memory=FakeMemory(),
        poster=FakePoster(),
        chooser=FakeChooser(),
        opener=FakeOpener(),
        tempfiles=FakeTempFiles(),
        probe=FakeProbe(),
    )


def test_empty_selection_sends_nothing() -> None:
    assert deliver_selection("   \n  ", _policy(), _deps()) == NothingToSend()


def test_single_session_is_injected_with_the_rendered_template() -> None:
    poster = FakePoster()
    registry = FakeRegistry(entries={Pid(10): entry(10)})
    deps = replace(_deps(), sessions=FakeSessions((session(10),)), registry=registry, poster=poster)
    result = deliver_selection("ls -la", _policy(), deps)
    assert isinstance(result, Injected)
    assert result.reason is PickReason.ONLY_SESSION
    assert result.chars == len("ls -la")
    (address, content) = poster.posts[0]
    assert address.pid == 10
    assert address.token == entry(10).token
    assert content == "Explain this:\nls -la\n(my own request)"


def test_injection_without_a_registry_entry_posts_as_unverified_peer() -> None:
    poster = FakePoster()
    deps = replace(_deps(), sessions=FakeSessions((session(10),)), poster=poster)
    result = deliver_selection("x", _policy(), deps)
    assert isinstance(result, Injected)
    (address, _content) = poster.posts[0]
    assert address.socket_path is None
    assert address.token is None


def test_no_live_session_opens_a_new_window() -> None:
    opener = FakeOpener()
    deps = replace(_deps(), opener=opener)
    result = deliver_selection("boom", _policy(), deps)
    assert isinstance(result, OpenedNewWindow)
    assert result.used_tempfile is False
    assert result.link_truncated is False
    url = opener.opened[0]
    assert url.startswith("claude-cli://open?cwd=")
    assert "explain-selection%3Aexplain" in url


def test_long_selection_with_truncate_policy_marks_the_link_truncated() -> None:
    opener = FakeOpener()
    deps = replace(_deps(), opener=opener)
    result = deliver_selection("z" * 6000, _policy(max_chars=6000), deps)
    assert isinstance(result, OpenedNewWindow)
    assert result.link_truncated is True
    assert result.truncated is False
    assert result.used_tempfile is False


def test_injection_reports_how_much_of_the_selection_survived_cleaning() -> None:
    deps = replace(_deps(), sessions=FakeSessions((session(10),)))
    result = deliver_selection("abcdefgh", _policy(max_chars=5), deps)
    assert isinstance(result, Injected)
    assert result.truncated is True
    assert result.original_chars == 8
    assert result.chars == len(clean_selection("abcdefgh", 5).text)


def test_injection_of_a_short_selection_is_not_truncated() -> None:
    deps = replace(_deps(), sessions=FakeSessions((session(10),)))
    result = deliver_selection("abc", _policy(max_chars=5), deps)
    assert isinstance(result, Injected)
    assert result.truncated is False
    assert result.original_chars == 3
    assert result.chars == 3


def test_new_window_reports_selection_truncation_separately_from_the_link() -> None:
    result = deliver_selection("abcdefgh", _policy(max_chars=5), _deps())
    assert isinstance(result, OpenedNewWindow)
    assert result.truncated is True
    assert result.original_chars == 8
    assert result.chars == len(clean_selection("abcdefgh", 5).text)
    assert result.link_truncated is False


def test_long_selection_with_tempfile_policy_references_the_file() -> None:
    opener = FakeOpener()
    tempfiles = FakeTempFiles(path="/tmp/sel-1.txt")
    deps = replace(_deps(), opener=opener, tempfiles=tempfiles)
    result = deliver_selection(
        "z" * 6000, _policy(max_chars=6000, long_selection=LongSelection.TEMPFILE), deps
    )
    assert isinstance(result, OpenedNewWindow)
    assert result.used_tempfile is True
    assert tempfiles.written == ["z" * 6000]
    assert "saved%20at%20%2Ftmp%2Fsel-1.txt" in opener.opened[0]


def test_terminal_tty_focus_selects_the_matching_session() -> None:
    poster = FakePoster()
    registry = FakeRegistry(
        entries={Pid(10): entry(10, tty="ttys005"), Pid(20): entry(20, tty="ttys006")}
    )
    deps = replace(
        _deps(),
        sessions=FakeSessions((session(10), session(20))),
        registry=registry,
        focus=FakeFocus(Focus(terminal_tty="ttys006", tmux_pane=None)),
        poster=poster,
    )
    result = deliver_selection("hi", _policy(), deps)
    assert isinstance(result, Injected)
    assert result.target.session.pid == 20
    assert result.reason is PickReason.TERMINAL_TTY


def test_device_path_from_the_terminal_matches_the_registry_tty_name() -> None:
    poster = FakePoster()
    registry = FakeRegistry(
        entries={Pid(10): entry(10, tty="ttys005"), Pid(20): entry(20, tty="ttys006")}
    )
    probe = OsascriptFocus(
        FakeRunner(queue=[CommandResult(returncode=0, stdout="/dev/ttys005\n", stderr="")])
    )
    deps = replace(
        _deps(),
        sessions=FakeSessions((session(10), session(20))),
        registry=registry,
        focus=probe,
        poster=poster,
    )
    result = deliver_selection("hi", _policy(), deps)
    assert isinstance(result, Injected)
    assert result.target.session.pid == 10
    assert result.reason is PickReason.TERMINAL_TTY


@pytest.mark.parametrize("live", [(), (session(10),)], ids=["none", "single"])
def test_unambiguous_cases_skip_the_focus_probe_and_the_memory(
    live: tuple[LiveSession, ...],
) -> None:
    focus = FakeFocus()
    memory = FakeMemory()
    deps = replace(_deps(), sessions=FakeSessions(live), focus=focus, memory=memory)
    deliver_selection("x", _policy(), deps)
    assert focus.probes == 0
    assert memory.loads == 0


def test_two_sessions_probe_the_focus_and_memory_once() -> None:
    focus = FakeFocus()
    memory = FakeMemory()
    deps = replace(
        _deps(),
        sessions=FakeSessions((session(10, name="a"), session(20, name="b"))),
        focus=focus,
        memory=memory,
        chooser=FakeChooser(choice=None),
    )
    deliver_selection("x", _policy(), deps)
    assert focus.probes == 1
    assert memory.loads == 1


def test_ambiguous_selection_asks_and_remembers_the_pick() -> None:
    sessions = FakeSessions((session(10, name="a"), session(20, name="b")))
    ordered = join_targets(sessions.sessions, ())
    pick_20 = next(t for t in ordered if t.session.pid == 20)
    poster = FakePoster()
    memory = FakeMemory()
    chooser = FakeChooser(choice=pick_20)
    deps = replace(_deps(), sessions=sessions, memory=memory, poster=poster, chooser=chooser)

    result = deliver_selection("pick me", _policy(), deps)
    assert isinstance(result, Injected)
    assert result.reason is PickReason.CHOSEN
    assert result.target.session.pid == 20
    assert memory.saved == [RememberedTarget(Pid(20), NOW)]
    assert poster.posts[0][0].pid == 20
    assert chooser.shown == [ordered]


def test_dismissing_the_chooser_cancels() -> None:
    memory = FakeMemory()
    poster = FakePoster()
    deps = replace(
        _deps(),
        sessions=FakeSessions((session(10, name="a"), session(20, name="b"))),
        memory=memory,
        poster=poster,
        chooser=FakeChooser(choice=None),
    )
    result = deliver_selection("x", _policy(), deps)
    assert isinstance(result, Cancelled)
    assert memory.saved == []
    assert poster.posts == []


def test_stale_registry_entries_are_pruned_against_live_sessions() -> None:
    registry = FakeRegistry(entries={Pid(10): entry(10), Pid(999): entry(999)})
    deps = replace(
        _deps(), sessions=FakeSessions((session(10),)), registry=registry, poster=FakePoster()
    )
    deliver_selection("x", _policy(), deps)
    assert Pid(999) in registry.deleted
    assert Pid(10) not in registry.deleted


def test_an_unlisted_but_alive_pid_keeps_its_entry_while_a_dead_one_is_pruned() -> None:
    registry = FakeRegistry(entries={Pid(10): entry(10), Pid(20): entry(20), Pid(999): entry(999)})
    probe = FakeProbe(alive={Pid(20)})
    deps = replace(_deps(), sessions=FakeSessions((session(10),)), registry=registry, probe=probe)
    deliver_selection("x", _policy(), deps)
    assert registry.deleted == [Pid(999)]
    assert sorted(probe.asked) == [Pid(20), Pid(999)]


def test_mode_a_prompt_uses_the_explain_skill_not_the_template() -> None:
    opener = FakeOpener()
    deps = replace(_deps(), opener=opener)
    deliver_selection("short thing", _policy(), deps)
    assert MODE_A_SKILL == "/explain-selection:explain"
    assert "Explain%20this" not in opener.opened[0]
