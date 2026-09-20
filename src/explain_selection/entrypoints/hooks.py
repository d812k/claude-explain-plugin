"""Shared plumbing for the SessionStart, CwdChanged and SessionEnd hook entrypoints.

Hooks must be quiet and quick: nothing on stdout (a SessionStart hook's stdout is injected
into the session), exit 0 in every case so a session never breaks, and pydantic plus the
adapters imported only when the hook actually runs.
"""

import logging
import os
from collections.abc import Callable, Mapping
from typing import Final, assert_never

from explain_selection.domain import InboxToken, SessionId
from explain_selection.entrypoints.runtime import (
    PACKAGE_LOGGER,
    checkout_root,
    configure_logging,
    read_stdin,
)
from explain_selection.services import (
    HookContext,
    RegisterDeps,
    Registered,
    RegisterResult,
    Skipped,
)

HookRunner = Callable[[str, Mapping[str, str], RegisterDeps], int]

SOCKET_VAR: Final[str] = "CLAUDE_CODE_MESSAGING_SOCKET"
TOKEN_VAR: Final[str] = "CLAUDE_CODE_MESSAGING_TOKEN"
SESSION_NAME_VAR: Final[str] = "CLAUDE_SESSION_NAME"

logger = logging.getLogger(__name__)


def build_hook_context(stdin_text: str, environ: Mapping[str, str]) -> HookContext:
    """Combine the hook's stdin JSON with the routing values Claude Code exports."""
    from explain_selection.adapters import parse_hook_stdin  # lazy: pulls in pydantic

    stdin = parse_hook_stdin(stdin_text)
    token = environ.get(TOKEN_VAR)
    return HookContext(
        session_id=SessionId(stdin.session_id) if stdin.session_id else None,
        cwd=stdin.cwd,
        name=environ.get(SESSION_NAME_VAR) or None,
        socket_path=environ.get(SOCKET_VAR) or None,
        token=InboxToken(token) if token else None,
        tmux=environ.get("TMUX") or None,
        tmux_pane=environ.get("TMUX_PANE") or None,
    )


def log_result(target: logging.Logger, event: str, result: RegisterResult) -> None:
    """Record the outcome without ever touching the token."""
    match result:
        case Registered(entry=entry):
            target.info(
                "%s: registered pid %d cwd=%s tty=%s pane=%s",
                event,
                entry.pid,
                entry.cwd,
                entry.tty,
                entry.tmux_pane,
            )
        case Skipped(reason=reason):
            target.info("%s: skipped: %s", event, reason)
        case _:
            assert_never(result)


def hook_main(run: HookRunner) -> int:
    """Build Settings and deps from the process, run one hook, and exit 0 whatever happens."""
    try:
        from explain_selection.adapters import SubprocessRunner
        from explain_selection.entrypoints.deps import build_register_deps
        from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

        environ = dict(os.environ)
        settings = load_settings(environ, resolve_plugin_root(environ, checkout_root()))
        configure_logging(settings.log_file, logging.getLogger(PACKAGE_LOGGER))
        deps = build_register_deps(settings, SubprocessRunner())
        return run(read_stdin(), environ, deps)
    except Exception:
        logger.exception("hook failed")
        return 0


__all__ = [
    "SESSION_NAME_VAR",
    "SOCKET_VAR",
    "TOKEN_VAR",
    "HookRunner",
    "build_hook_context",
    "hook_main",
    "log_result",
]
