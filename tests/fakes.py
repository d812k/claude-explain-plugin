"""In-memory fakes implementing the service protocols. No mocks of internals."""

from dataclasses import dataclass, field

from explain_selection.domain import (
    Focus,
    LiveSession,
    Pid,
    RegistryEntry,
    RememberedTarget,
    Target,
)
from explain_selection.errors import InboxUnavailableError
from explain_selection.services import InboxAddress


@dataclass(slots=True)
class FakeClock:
    """A clock frozen at a fixed instant."""

    now: int = 1_700_000_600_000

    def now_ms(self) -> int:
        return self.now


@dataclass(slots=True)
class FakeSessions:
    """Returns a fixed list of live sessions."""

    sessions: tuple[LiveSession, ...] = ()

    def list_interactive(self) -> tuple[LiveSession, ...]:
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
    """Returns a fixed focus signal."""

    focus: Focus = field(default_factory=lambda: Focus(terminal_tty=None, tmux_pane=None))

    def probe(self) -> Focus:
        return self.focus


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

    def load(self) -> RememberedTarget | None:
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
