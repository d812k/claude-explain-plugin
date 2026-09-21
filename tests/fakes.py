"""In-memory fakes implementing the service and adapter protocols. No mocks of internals."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from explain_selection.adapters import CommandResult
from explain_selection.domain import (
    FileFacts,
    Focus,
    LiveSession,
    Pid,
    RegistryEntry,
    RememberedTarget,
    Target,
)
from explain_selection.errors import (
    AgentsQueryError,
    InboxUnavailableError,
    InstallError,
    SubprocessError,
)
from explain_selection.services import ClaudeSettingsFacts, InboxAddress

MISSING = FileFacts(
    exists=False, mode=None, is_dir=False, is_socket=False, is_executable=False, readable=False
)


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

    def list_live(self) -> tuple[LiveSession, ...]:
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


@dataclass(slots=True)
class FakeInstallFiles:
    """An in-memory install file layer: records every write; can pre-populate or fail paths."""

    existing: set[Path] = field(default_factory=set[Path])
    fail_paths: set[Path] = field(default_factory=set[Path])
    dirs: list[Path] = field(default_factory=list[Path])
    written: dict[Path, tuple[str, int]] = field(default_factory=dict[Path, tuple[str, int]])
    copied: list[tuple[Path, Path]] = field(default_factory=list[tuple[Path, Path]])
    replaced: list[tuple[Path, Path]] = field(default_factory=list[tuple[Path, Path]])

    def ensure_private_dir(self, path: Path) -> None:
        self._check(path)
        self.dirs.append(path)

    def exists(self, path: Path) -> bool:
        return (
            path in self.existing
            or path in self.written
            or any(dst == path for _, dst in self.copied)
        )

    def write_private_file(self, path: Path, content: str, mode: int) -> None:
        self._check(path)
        self.written[path] = (content, mode)

    def copy_file(self, src: Path, dst: Path) -> None:
        self._check(dst)
        self.copied.append((src, dst))

    def replace_tree(self, src: Path, dst: Path) -> None:
        self._check(dst)
        self.replaced.append((src, dst))

    @property
    def touched(self) -> bool:
        return bool(self.dirs or self.written or self.copied or self.replaced)

    def _check(self, path: Path) -> None:
        if path in self.fail_paths:
            raise InstallError(f"permission denied: {path}")


@dataclass(slots=True)
class FakeRegistrar:
    """A macOS Services registrar that records calls and answers a canned status."""

    status: str = ""
    fail: bool = False
    shortcuts: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    refreshes: int = 0

    def set_shortcut(self, service_name: str, key: str) -> None:
        if self.fail:
            raise InstallError("defaults write failed")
        self.shortcuts.append((service_name, key))

    def refresh(self) -> None:
        self.refreshes += 1

    def read_status(self) -> str:
        return self.status


@dataclass(slots=True)
class FakeFiles:
    """A read-only file inspector over two tables; a path in neither does not exist."""

    facts: dict[Path, FileFacts] = field(default_factory=dict[Path, FileFacts])
    texts: dict[Path, str] = field(default_factory=dict[Path, str])
    inspected: list[Path] = field(default_factory=list[Path])

    def inspect(self, path: Path) -> FileFacts:
        self.inspected.append(path)
        return self.facts.get(path, MISSING)

    def read_text(self, path: Path) -> str | None:
        return self.texts.get(path)


@dataclass(slots=True)
class FakeVersions:
    """Answers a fixed installed version; records which interpreters it was asked about."""

    version: str | None = "0.1.0"
    asked: list[Path] = field(default_factory=list[Path])

    def installed_version(self, python: Path) -> str | None:
        self.asked.append(python)
        return self.version


@dataclass(slots=True)
class FakeClaudeSettings:
    """Returns fixed Claude Code settings facts."""

    facts: ClaudeSettingsFacts = field(
        default_factory=lambda: ClaudeSettingsFacts(cross_session_inbound=None, plugin_enabled=True)
    )

    def read(self) -> ClaudeSettingsFacts:
        return self.facts


@dataclass(slots=True)
class FakeMac:
    """A macOS probe with canned answers."""

    bundle_facts: FileFacts = MISSING
    status: str | None = None
    osascript: bool = True

    def bundle(self) -> FileFacts:
        return self.bundle_facts

    def shortcut_status(self) -> str | None:
        return self.status

    def osascript_found(self) -> bool:
        return self.osascript
