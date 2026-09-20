"""Property tests: target selection is total, closed over its input, and order-independent."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from explain_selection.domain import (
    Choose,
    Focus,
    Inject,
    OpenNewWindow,
    Pid,
    RememberedTarget,
    SessionKind,
    SessionStatus,
    Target,
    join_targets,
    select_target,
)
from tests.builders import entry, session

NOW = 1_700_000_600_000
TTL = 600_000

pids = st.integers(min_value=2, max_value=60)
ttys = st.sampled_from(["ttys000", "ttys001", "ttys002", "pts/3"])
panes = st.sampled_from(["%0", "%1", "%2"])


@st.composite
def targets(draw: st.DrawFn) -> tuple[Target, ...]:
    chosen = draw(st.lists(pids, unique=True, max_size=6))
    sessions = [
        session(
            pid,
            status=draw(st.sampled_from(list(SessionStatus))),
            kind=draw(st.sampled_from(list(SessionKind))),
            name=draw(st.one_of(st.none(), st.text(max_size=5))),
            cwd=draw(st.sampled_from(["/a", "/b", "/c"])),
        )
        for pid in chosen
    ]
    entries = [
        entry(
            pid,
            tty=draw(st.one_of(st.none(), ttys)),
            tmux_pane=draw(st.one_of(st.none(), panes)),
        )
        for pid in chosen
        if draw(st.booleans())
    ]
    return join_targets(sessions, entries)


focuses = st.builds(
    Focus, terminal_tty=st.one_of(st.none(), ttys), tmux_pane=st.one_of(st.none(), panes)
)
remembereds = st.one_of(
    st.none(),
    st.builds(
        RememberedTarget,
        pid=pids.map(Pid),
        chosen_at_ms=st.integers(min_value=NOW - 2 * TTL, max_value=NOW + TTL),
    ),
)


@pytest.mark.prop
@given(ts=targets(), focus=focuses, remembered=remembereds)
def test_decision_is_drawn_from_the_candidates(
    ts: tuple[Target, ...], focus: Focus, remembered: RememberedTarget | None
) -> None:
    decision = select_target(ts, focus, remembered, NOW, TTL)
    match decision:
        case OpenNewWindow():
            assert ts == ()
        case Inject(target=target):
            assert target in ts
        case Choose(options=options):
            assert len(options) > 1
            assert set(options) <= set(ts)
            assert len(set(options)) == len(options)


@pytest.mark.prop
@given(ts=targets(), focus=focuses, remembered=remembereds, data=st.data())
def test_decision_does_not_depend_on_candidate_order(
    ts: tuple[Target, ...],
    focus: Focus,
    remembered: RememberedTarget | None,
    data: st.DataObject,
) -> None:
    shuffled = data.draw(st.permutations(list(ts)))
    assert select_target(shuffled, focus, remembered, NOW, TTL) == select_target(
        ts, focus, remembered, NOW, TTL
    )


@pytest.mark.prop
@given(ts=targets(), focus=focuses)
def test_only_interactive_sessions_become_targets(ts: tuple[Target, ...], focus: Focus) -> None:
    assert all(t.session.kind is SessionKind.INTERACTIVE for t in ts)
