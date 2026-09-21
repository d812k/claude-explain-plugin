"""Target selection follows the ladder: focus, then memory, then idleness, then ask."""

from explain_selection.domain import (
    Choose,
    Focus,
    Inject,
    OpenNewWindow,
    PickReason,
    Pid,
    RememberedTarget,
    SessionKind,
    SessionStatus,
    Target,
    chooser_order,
    describe_target,
    join_targets,
    select_target,
)
from tests.builders import entry, session

NO_FOCUS = Focus(terminal_tty=None, tmux_pane=None)
NOW = 1_700_000_600_000
TTL = 10 * 60 * 1000


def test_no_live_session_falls_back_to_a_new_window() -> None:
    assert select_target((), NO_FOCUS, None, NOW, TTL) == OpenNewWindow()


def test_a_single_session_is_used_without_any_signal() -> None:
    targets = join_targets([session(10, status=SessionStatus.BUSY)], [])
    decision = select_target(targets, NO_FOCUS, None, NOW, TTL)
    assert decision == Inject(targets[0], PickReason.ONLY_SESSION)


def test_join_drops_background_sessions_and_stale_entries() -> None:
    targets = join_targets(
        [session(10), session(20, kind=SessionKind.BACKGROUND)],
        [entry(10, tty="ttys005"), entry(99)],
    )
    assert [t.session.pid for t in targets] == [10]
    assert targets[0].entry == entry(10, tty="ttys005")


def test_join_keeps_background_sessions_when_asked_to() -> None:
    targets = join_targets(
        [session(20, kind=SessionKind.BACKGROUND), session(10)],
        [entry(20), entry(99)],
        include_background=True,
    )
    assert [(t.session.pid, t.session.kind) for t in targets] == [
        (10, SessionKind.INTERACTIVE),
        (20, SessionKind.BACKGROUND),
    ]
    assert [t.entry for t in targets] == [None, entry(20)]


def test_join_leaves_entry_empty_when_the_hook_never_ran() -> None:
    targets = join_targets([session(10)], [])
    assert targets == (Target(session(10), None),)


def test_tmux_pane_focus_picks_the_session_in_that_pane() -> None:
    targets = join_targets(
        [session(10), session(20)], [entry(10, tmux_pane="%3"), entry(20, tmux_pane="%7")]
    )
    focus = Focus(terminal_tty="ttys001", tmux_pane="%7")
    decision = select_target(targets, focus, None, NOW, TTL)
    assert decision == Inject(targets[1], PickReason.TMUX_PANE)


def test_terminal_tty_focus_picks_the_session_on_that_tty() -> None:
    targets = join_targets(
        [session(10, status=SessionStatus.BUSY), session(20)],
        [entry(10, tty="ttys005"), entry(20, tty="ttys006")],
    )
    focus = Focus(terminal_tty="ttys005", tmux_pane=None)
    decision = select_target(targets, focus, None, NOW, TTL)
    assert decision == Inject(targets[0], PickReason.TERMINAL_TTY)


def test_focus_that_matches_nothing_is_ignored() -> None:
    targets = join_targets([session(10), session(20)], [entry(10, tty="ttys005")])
    focus = Focus(terminal_tty="ttys009", tmux_pane="%1")
    decision = select_target(targets, focus, None, NOW, TTL)
    assert decision == Choose(targets)


def test_recent_remembered_pick_wins_over_idleness() -> None:
    targets = join_targets([session(10, status=SessionStatus.BUSY), session(20)], [])
    remembered = RememberedTarget(pid=Pid(10), chosen_at_ms=NOW - TTL)
    decision = select_target(targets, NO_FOCUS, remembered, NOW, TTL)
    assert decision == Inject(targets[0], PickReason.REMEMBERED)


def test_expired_remembered_pick_is_ignored() -> None:
    targets = join_targets([session(10, status=SessionStatus.BUSY), session(20)], [])
    remembered = RememberedTarget(pid=Pid(10), chosen_at_ms=NOW - TTL - 1)
    decision = select_target(targets, NO_FOCUS, remembered, NOW, TTL)
    assert decision == Inject(targets[1], PickReason.ONLY_IDLE)


def test_remembered_pick_from_the_future_is_ignored() -> None:
    targets = join_targets([session(10, status=SessionStatus.BUSY), session(20)], [])
    remembered = RememberedTarget(pid=Pid(10), chosen_at_ms=NOW + 1)
    decision = select_target(targets, NO_FOCUS, remembered, NOW, TTL)
    assert decision == Inject(targets[1], PickReason.ONLY_IDLE)


def test_remembered_pick_of_a_dead_session_is_ignored() -> None:
    targets = join_targets([session(10, status=SessionStatus.BUSY), session(20)], [])
    remembered = RememberedTarget(pid=Pid(99), chosen_at_ms=NOW)
    decision = select_target(targets, NO_FOCUS, remembered, NOW, TTL)
    assert decision == Inject(targets[1], PickReason.ONLY_IDLE)


def test_the_only_idle_session_is_preferred_over_busy_ones() -> None:
    targets = join_targets(
        [
            session(10, status=SessionStatus.BUSY),
            session(20, status=SessionStatus.WAITING),
            session(30),
        ],
        [],
    )
    decision = select_target(targets, NO_FOCUS, None, NOW, TTL)
    assert decision == Inject(targets[2], PickReason.ONLY_IDLE)


def test_several_idle_sessions_are_offered_without_the_busy_ones() -> None:
    targets = join_targets(
        [session(10, status=SessionStatus.BUSY), session(20, name="b"), session(30, name="a")],
        [],
    )
    decision = select_target(targets, NO_FOCUS, None, NOW, TTL)
    assert decision == Choose((targets[2], targets[1]))


def test_all_busy_sessions_are_offered_idle_first_then_busy_then_waiting() -> None:
    targets = join_targets(
        [
            session(10, status=SessionStatus.WAITING),
            session(20, status=SessionStatus.BUSY),
            session(30, status=SessionStatus.BUSY),
        ],
        [],
    )
    decision = select_target(targets, NO_FOCUS, None, NOW, TTL)
    assert decision == Choose((targets[1], targets[2], targets[0]))
    assert decision == Choose(tuple(sorted(targets, key=chooser_order)))


def test_chooser_order_ranks_status_then_name_then_cwd_then_pid() -> None:
    targets = join_targets(
        [
            session(1, status=SessionStatus.WAITING, name="a"),
            session(2, status=SessionStatus.BUSY, name="z"),
            session(3, name="b", cwd="/x"),
            session(4, name="b", cwd="/w"),
            session(6, name="b", cwd="/w"),
            session(5, name="a"),
        ],
        [],
    )
    assert [t.session.pid for t in sorted(targets, key=chooser_order)] == [5, 4, 6, 3, 2, 1]


def test_tmux_focus_narrows_before_the_idle_heuristic_applies() -> None:
    targets = join_targets(
        [
            session(10, status=SessionStatus.BUSY),
            session(20, status=SessionStatus.BUSY),
            session(30),
        ],
        [entry(10, tmux_pane="%7"), entry(20, tmux_pane="%7")],
    )
    focus = Focus(terminal_tty=None, tmux_pane="%7")
    decision = select_target(targets, focus, None, NOW, TTL)
    assert decision == Choose((targets[0], targets[1]))


def test_describe_uses_name_when_present_and_directory_otherwise() -> None:
    named = Target(session(10, name="hmac", cwd="/home/me/proj"), None)
    unnamed = Target(session(20, cwd="/home/me/proj", status=SessionStatus.BUSY), None)
    assert describe_target(named) == "hmac - /home/me/proj (idle)"
    assert describe_target(unnamed) == "proj - /home/me/proj (busy)"
