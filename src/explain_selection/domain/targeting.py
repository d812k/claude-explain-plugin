"""Pure target selection: which live session should receive the selected text.

The ladder follows the design plan, section 4.7 and 4.8, refined as follows:
an explicit focus signal (tmux pane, then terminal tty) beats a remembered pick,
which beats the idle heuristic, which beats asking the user. Every step narrows the
candidate set and returns as soon as exactly one candidate remains.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Final

from explain_selection.domain.models import (
    LiveSession,
    Pid,
    RegistryEntry,
    SessionKind,
    SessionStatus,
)


@dataclass(frozen=True, slots=True)
class Target:
    """A live interactive session joined with its registry entry, if the hook wrote one."""

    session: LiveSession
    entry: RegistryEntry | None


@dataclass(frozen=True, slots=True)
class Focus:
    """What the hotkey could learn about where the user is looking."""

    terminal_tty: str | None
    tmux_pane: str | None


@dataclass(frozen=True, slots=True)
class RememberedTarget:
    """The user's last explicit pick from the chooser."""

    pid: Pid
    chosen_at_ms: int


class PickReason(Enum):
    """Why a single target was selected without asking."""

    ONLY_SESSION = "only_session"
    TMUX_PANE = "tmux_pane"
    TERMINAL_TTY = "terminal_tty"
    REMEMBERED = "remembered"
    ONLY_IDLE = "only_idle"


@dataclass(frozen=True, slots=True)
class Inject:
    """Deliver into exactly this session."""

    target: Target
    reason: PickReason


@dataclass(frozen=True, slots=True)
class Choose:
    """Ambiguous: ask the user to pick one of these, best candidates first."""

    options: tuple[Target, ...]


@dataclass(frozen=True, slots=True)
class OpenNewWindow:
    """No live interactive session: fall back to the deep link."""


Decision = Inject | Choose | OpenNewWindow

_STATUS_RANK: Final[dict[SessionStatus, int]] = {
    SessionStatus.IDLE: 0,
    SessionStatus.BUSY: 1,
    SessionStatus.WAITING: 2,
}


def join_targets(
    sessions: Iterable[LiveSession], entries: Iterable[RegistryEntry]
) -> tuple[Target, ...]:
    """Pair interactive sessions with registry entries by pid; drop everything else."""
    by_pid = {entry.pid: entry for entry in entries}
    interactive = (s for s in sessions if s.kind is SessionKind.INTERACTIVE)
    return tuple(
        Target(session=s, entry=by_pid.get(s.pid)) for s in sorted(interactive, key=_pid_of)
    )


def select_target(
    targets: Iterable[Target],
    focus: Focus,
    remembered: RememberedTarget | None,
    now_ms: int,
    remember_ttl_ms: int,
) -> Decision:
    """Decide where the text goes; see the module docstring for the ladder."""
    candidates = tuple(targets)
    if not candidates:
        return OpenNewWindow()
    if len(candidates) == 1:
        return Inject(candidates[0], PickReason.ONLY_SESSION)

    steps: tuple[tuple[PickReason, Callable[[Target], bool]], ...] = (
        (PickReason.TMUX_PANE, _pane_matcher(focus.tmux_pane)),
        (PickReason.TERMINAL_TTY, _tty_matcher(focus.terminal_tty)),
    )
    for reason, matches in steps:
        narrowed = tuple(c for c in candidates if matches(c))
        if len(narrowed) == 1:
            return Inject(narrowed[0], reason)
        if narrowed:
            candidates = narrowed

    if remembered is not None and 0 <= now_ms - remembered.chosen_at_ms <= remember_ttl_ms:
        hits = tuple(c for c in candidates if c.session.pid == remembered.pid)
        if len(hits) == 1:
            return Inject(hits[0], PickReason.REMEMBERED)

    idle = tuple(c for c in candidates if c.session.status is SessionStatus.IDLE)
    if len(idle) == 1:
        return Inject(idle[0], PickReason.ONLY_IDLE)
    if idle:
        candidates = idle
    return Choose(tuple(sorted(candidates, key=_display_order)))


def describe_target(target: Target) -> str:
    """One line for the chooser: name, working directory and status."""
    session = target.session
    label = session.name or session.cwd.rsplit("/", 1)[-1] or session.cwd
    return f"{label} - {session.cwd} ({session.status.value})"


def _pane_matcher(pane: str | None) -> Callable[[Target], bool]:
    def matches(target: Target) -> bool:
        return pane is not None and target.entry is not None and target.entry.tmux_pane == pane

    return matches


def _tty_matcher(tty: str | None) -> Callable[[Target], bool]:
    def matches(target: Target) -> bool:
        return tty is not None and target.entry is not None and target.entry.tty == tty

    return matches


def _pid_of(session: LiveSession) -> int:
    return session.pid


def _display_order(target: Target) -> tuple[int, str, str, int]:
    session = target.session
    return (_STATUS_RANK[session.status], session.name or "", session.cwd, session.pid)


__all__ = [
    "Choose",
    "Decision",
    "Focus",
    "Inject",
    "OpenNewWindow",
    "PickReason",
    "RememberedTarget",
    "Target",
    "describe_target",
    "join_targets",
    "select_target",
]
