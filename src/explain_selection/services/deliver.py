"""Use case: take a raw selection and deliver it to the right session, or a new window.

This composes the pure target-selection ladder with the injected side effects. Mode B
(inject into a live session) is the primary path; mode A (open a new window via the deep
link) is the fallback when no session is live. When several sessions match and no signal
disambiguates, the user is asked and the pick is remembered.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, assert_never

from explain_selection.domain import (
    DEEP_LINK_QUERY_LIMIT,
    Choose,
    Focus,
    Inject,
    OpenNewWindow,
    PickReason,
    RememberedTarget,
    Selection,
    Target,
    build_deep_link,
    clean_selection,
    fit_prompt_for_deep_link,
    join_targets,
    render_prompt,
    select_target,
)
from explain_selection.services.protocols import (
    Chooser,
    Clock,
    FocusProbe,
    InboxAddress,
    InboxPoster,
    LinkOpener,
    RegistryStore,
    SessionLister,
    TargetMemory,
    TempFileWriter,
)

MODE_A_SKILL: Final[str] = "/explain-selection:explain"


class LongSelection(Enum):
    """What mode A does when the selection exceeds the deep link's query limit."""

    TRUNCATE = "truncate"
    TEMPFILE = "tempfile"


@dataclass(frozen=True, slots=True)
class DeliveryPolicy:
    """The knobs that shape delivery, resolved from settings once per run."""

    max_chars: int
    prompt_template: str
    remember_ttl_ms: int
    long_selection: LongSelection
    fallback_cwd: str


@dataclass(frozen=True, slots=True)
class DeliverDeps:
    """Every side effect delivery needs, injected once."""

    clock: Clock
    sessions: SessionLister
    registry: RegistryStore
    focus: FocusProbe
    memory: TargetMemory
    poster: InboxPoster
    chooser: Chooser
    opener: LinkOpener
    tempfiles: TempFileWriter


@dataclass(frozen=True, slots=True)
class Injected:
    """The selection was posted into a live session."""

    target: Target
    reason: PickReason
    chars: int


@dataclass(frozen=True, slots=True)
class OpenedNewWindow:
    """No live session; a new window was opened via the deep link."""

    cwd: str
    used_tempfile: bool
    truncated: bool


@dataclass(frozen=True, slots=True)
class Cancelled:
    """Several sessions matched and the user dismissed the chooser."""


@dataclass(frozen=True, slots=True)
class NothingToSend:
    """The selection was empty after cleaning."""


Outcome = Injected | OpenedNewWindow | Cancelled | NothingToSend


def deliver_selection(raw: str, policy: DeliveryPolicy, deps: DeliverDeps) -> Outcome:
    """Clean ``raw`` and deliver it; see the module docstring for the routing."""
    selection = clean_selection(raw, policy.max_chars)
    if not selection.text:
        return NothingToSend()

    sessions = deps.sessions.list_interactive()
    entries = deps.registry.read_all()
    live_pids = {s.pid for s in sessions}
    for entry in entries:
        if entry.pid not in live_pids:
            deps.registry.delete(entry.pid)

    targets = join_targets(sessions, entries)
    # The ladder only consults focus and memory with two or more candidates; skipping the
    # probes otherwise saves an osascript run (and its Automation prompt) and tmux calls.
    ambiguous = len(targets) > 1
    focus = deps.focus.probe() if ambiguous else Focus(terminal_tty=None, tmux_pane=None)
    remembered = deps.memory.load() if ambiguous else None
    decision = select_target(
        targets, focus, remembered, deps.clock.now_ms(), policy.remember_ttl_ms
    )

    match decision:
        case OpenNewWindow():
            return _open_new_window(selection, policy, deps)
        case Inject(target=target, reason=reason):
            _inject(target, selection, policy, deps)
            return Injected(target, reason, len(selection.text))
        case Choose(options=options):
            chosen = deps.chooser.choose(options)
            if chosen is None:
                return Cancelled()
            deps.memory.save(RememberedTarget(chosen.session.pid, deps.clock.now_ms()))
            _inject(chosen, selection, policy, deps)
            return Injected(chosen, PickReason.CHOSEN, len(selection.text))
        case _:
            assert_never(decision)


def _inject(
    target: Target, selection: Selection, policy: DeliveryPolicy, deps: DeliverDeps
) -> None:
    message = render_prompt(policy.prompt_template, selection)
    entry = target.entry
    address = InboxAddress(
        pid=target.session.pid,
        socket_path=entry.socket if entry is not None else None,
        token=entry.token if entry is not None else None,
    )
    deps.poster.post(address, message)


def _open_new_window(
    selection: Selection, policy: DeliveryPolicy, deps: DeliverDeps
) -> OpenedNewWindow:
    prompt = f"{MODE_A_SKILL} {selection.text}"
    if len(prompt) <= DEEP_LINK_QUERY_LIMIT:
        deps.opener.open(build_deep_link(policy.fallback_cwd, prompt))
        return OpenedNewWindow(policy.fallback_cwd, used_tempfile=False, truncated=False)
    if policy.long_selection is LongSelection.TEMPFILE:
        path = deps.tempfiles.write(selection.text)
        prompt = f"{MODE_A_SKILL} the selection saved at {path}"
        deps.opener.open(build_deep_link(policy.fallback_cwd, fit_prompt_for_deep_link(prompt)))
        return OpenedNewWindow(policy.fallback_cwd, used_tempfile=True, truncated=False)
    deps.opener.open(build_deep_link(policy.fallback_cwd, fit_prompt_for_deep_link(prompt)))
    return OpenedNewWindow(policy.fallback_cwd, used_tempfile=False, truncated=True)


__all__ = [
    "MODE_A_SKILL",
    "Cancelled",
    "DeliverDeps",
    "DeliveryPolicy",
    "Injected",
    "LongSelection",
    "NothingToSend",
    "OpenedNewWindow",
    "Outcome",
    "deliver_selection",
]
