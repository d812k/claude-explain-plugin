"""Side effects: Unix sockets, subprocesses, registry files, tmux."""

from explain_selection.adapters.agents_cli import AgentsCli
from explain_selection.adapters.clock import SystemClock
from explain_selection.adapters.focus import PaneLookup, TmuxAwareFocus
from explain_selection.adapters.hook_input import HookStdin, parse_hook_stdin
from explain_selection.adapters.inbox_socket import (
    InboxSocketPoster,
    SocketConnector,
    UnixSocketConnector,
)
from explain_selection.adapters.install_files import LocalInstallFiles
from explain_selection.adapters.opener import OpenLinkOpener
from explain_selection.adapters.osascript import (
    OsascriptChooser,
    OsascriptFocus,
    OsascriptNotifier,
)
from explain_selection.adapters.process_probe import OsProcessProbe
from explain_selection.adapters.ps import PsTtyLookup
from explain_selection.adapters.registry_files import RegistryFiles
from explain_selection.adapters.subprocess_runner import (
    CommandResult,
    CommandRunner,
    SubprocessRunner,
)
from explain_selection.adapters.target_memory import FileTargetMemory
from explain_selection.adapters.temp_files import TempFiles
from explain_selection.adapters.tmux import TmuxPanes

__all__ = [
    "AgentsCli",
    "CommandResult",
    "CommandRunner",
    "FileTargetMemory",
    "HookStdin",
    "InboxSocketPoster",
    "LocalInstallFiles",
    "OpenLinkOpener",
    "OsProcessProbe",
    "OsascriptChooser",
    "OsascriptFocus",
    "OsascriptNotifier",
    "PaneLookup",
    "PsTtyLookup",
    "RegistryFiles",
    "SocketConnector",
    "SubprocessRunner",
    "SystemClock",
    "TempFiles",
    "TmuxAwareFocus",
    "TmuxPanes",
    "UnixSocketConnector",
    "parse_hook_stdin",
]
