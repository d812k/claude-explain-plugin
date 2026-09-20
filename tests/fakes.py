"""In-memory fakes implementing the service and adapter protocols. No mocks of internals."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from explain_selection.adapters import CommandResult
from explain_selection.domain import (
    Focus,
    LiveSession,
    Pid,
    RegistryEntry,
    RememberedTarget,
    Target,
)
from explain_selection.errors import AgentsQueryError, InboxUnavailableError, SubprocessError
from explain_selection.services import InboxAddress


@dataclass(slots=True)
class FakeClock:
    """A clock frozen at a fixed instant."""

    now: int = 1_700_000_600_000

    def now_ms(self) -> int:
        return self.now


@dataclass(slots=True)
class FakeSessions:
    """Returns a fixed list of live sessions; can be told to fail like a broken ``claude``."""

    sessions: tuple[LiveSession, ...] = ()
    fail: bool = False

    def list_interactive(self) -> tuple[LiveSession, ...]:
        if self.fail:
            raise AgentsQueryError("claude agents failed")
        return self.sessions


@dataclass(slots=True)
class FakeRegistry:
    """A dict-backed registry, recording deletes for assertions."""

    entries: dict[Pid, RegistryEntry] = field(default_factory=dict[Pid, RegistryEntry])
    deleted: list[Pid] = field(default_factory=list[Pid])

    def save(self, entry: RegistryEntry) -> None:
        self.entries[entry.pid] = entry

    def delete(self, pid: Pid) -> None:
        self.deleted.append(pid)
        self.entries.pop(pid, None)

    def read_all(self) -> tuple[RegistryEntry, ...]:
        return tuple(self.entries.values())


@dataclass(slots=True)
class FakeProbe:
    """Reports the pids in ``alive`` as running; records every pid it was asked about."""

    alive: set[Pid] = field(default_factory=set[Pid])
    asked: list[Pid] = field(default_factory=list[Pid])

    def is_alive(self, pid: Pid) -> bool:
        self.asked.append(pid)
        return pid in self.alive


@dataclass(slots=True)
class FakeTtyLookup:
    """Maps pid to tty from a fixed table."""

    ttys: dict[Pid, str] = field(default_factory=dict[Pid, str])

    def tty_for(self, pid: Pid) -> str | None:
        return self.ttys.get(pid)


@dataclass(slots=True)
class FakePoster:
    """Records posts; can be told to fail like a dead socket."""

    posts: list[tuple[InboxAddress, str]] = field(default_factory=list[tuple[InboxAddress, str]])
    fail: bool = False

    def post(self, address: InboxAddress, content: str) -> None:
        if self.fail:
            raise InboxUnavailableError(f"no socket for pid {address.pid}")
        self.posts.append((address, content))


@dataclass(slots=True)
class FakeFocus:
    """Returns a fixed focus signal; counts how often it was probed."""

    focus: Focus = field(default_factory=lambda: Focus(terminal_tty=None, tmux_pane=None))
    probes: int = 0

    def probe(self) -> Focus:
        self.probes += 1
        return self.focus


@dataclass(slots=True)
class FakePanes:
    """A tmux pane lookup returning a fixed pane; records the ttys it was asked about."""

    pane: str | None = None
    fail: bool = False
    seen: list[str] = field(default_factory=list[str])

    def active_pane_for_tty(self, tty: str) -> str | None:
        self.seen.append(tty)
        if self.fail:
            raise SubprocessError("could not run tmux")
        return self.pane


@dataclass(slots=True)
class FakeChooser:
    """Returns a pre-set choice; records the options it was shown."""

    choice: Target | None = None
    shown: list[tuple[Target, ...]] = field(default_factory=list[tuple[Target, ...]])

    def choose(self, options: tuple[Target, ...]) -> Target | None:
        self.shown.append(options)
        return self.choice


@dataclass(slots=True)
class FakeMemory:
    """A single remembered pick held in memory."""

    remembered: RememberedTarget | None = None
    saved: list[RememberedTarget] = field(default_factory=list[RememberedTarget])
    loads: int = 0

    def load(self) -> RememberedTarget | None:
        self.loads += 1
        return self.remembered

    def save(self, remembered: RememberedTarget) -> None:
        self.saved.append(remembered)
        self.remembered = remembered


@dataclass(slots=True)
class FakeOpener:
    """Records the URLs it was asked to open."""

    opened: list[str] = field(default_factory=list[str])

    def open(self, url: str) -> None:
        self.opened.append(url)


@dataclass(slots=True)
class FakeTempFiles:
    """Records writes and returns a fixed path."""

    path: str = "/tmp/explain-selection-fake.txt"
    written: list[str] = field(default_factory=list[str])

    def write(self, text: str) -> str:
        self.written.append(text)
        return self.path


@dataclass(slots=True)
class FakeNotifier:
    """Records notifications; can be told to fail like a missing osascript."""

    shown: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    fail: bool = False

    def notify(self, title: str, message: str) -> None:
        if self.fail:
            raise SubprocessError("could not run osascript")
        self.shown.append((title, message))


@dataclass(slots=True)
class FakeRunner:
    """A command runner that replays a queue of results and records every call."""

    queue: list[CommandResult] = field(default_factory=list[CommandResult])
    calls: list[tuple[str, ...]] = field(default_factory=list[tuple[str, ...]])

    def run(
        self, args: Sequence[str], *, timeout: float, stdin: str | None = None
    ) -> CommandResult:
        self.calls.append(tuple(args))
        if self.queue:
            return self.queue.pop(0)
        return CommandResult(returncode=0, stdout="", stderr="")


@dataclass(slots=True)
class FakeConnector:
    """A Unix-socket connector fake: sends unless the path is marked to fail."""

    fail_paths: set[str] = field(default_factory=set[str])
    sent: list[tuple[str, bytes]] = field(default_factory=list[tuple[str, bytes]])

    def send(self, path: str, payload: bytes, *, timeout: float) -> None:
        if path in self.fail_paths:
            raise OSError(f"connection refused: {path}")
        self.sent.append((path, payload))
