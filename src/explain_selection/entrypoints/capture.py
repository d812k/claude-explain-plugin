"""Hotkey entrypoint: deliver the selected text to the right Claude Code session.

``argv`` is either empty or ``--text -`` (read the selection from stdin) or ``--text <string>``.
The exit code is always 0: the hotkey runner has nowhere to show it. Problems, and
injections into a session that is not idle, are reported as a macOS notification and
logged; a failing notifier is only logged.
"""

import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, assert_never

from explain_selection.domain import DEEP_LINK_QUERY_LIMIT, SessionStatus, describe_target
from explain_selection.entrypoints.runtime import (
    checkout_root,
    configure_logging,
    entrypoint_logger,
    read_stdin,
)
from explain_selection.services import (
    Cancelled,
    DeliverDeps,
    DeliveryPolicy,
    Injected,
    NothingToSend,
    Notifier,
    OpenedNewWindow,
    Outcome,
    deliver_selection,
)

if TYPE_CHECKING:
    from explain_selection.entrypoints.settings import Settings

logger = logging.getLogger(__name__)

NOTIFICATION_TITLE: Final[str] = "Explain selection"
USAGE: Final[str] = "usage: explain-selection-capture [--text -|<string>]"
TEXT_FLAG: Final[str] = "--text"
STDIN_MARKER: Final[str] = "-"


@dataclass(frozen=True, slots=True)
class FromStdin:
    """The selection arrives on stdin."""


@dataclass(frozen=True, slots=True)
class FromArgument:
    """The selection was passed on the command line."""

    text: str


@dataclass(frozen=True, slots=True)
class BadUsage:
    """The arguments did not match the usage line."""

    message: str


InputSource = FromStdin | FromArgument | BadUsage


def parse_argv(argv: Sequence[str]) -> InputSource:
    """Map ``argv`` (without the program name) to where the selection comes from."""
    match list(argv):
        case []:
            return FromStdin()
        case [flag, marker] if flag == TEXT_FLAG and marker == STDIN_MARKER:
            return FromStdin()
        case [flag, text] if flag == TEXT_FLAG:
            return FromArgument(text)
        case _:
            return BadUsage(f"{USAGE}; got {list(argv)!r}")


def build_policy(settings: "Settings") -> DeliveryPolicy:
    """Turn Settings into the delivery policy, reading the prompt template file once."""
    return DeliveryPolicy(
        max_chars=settings.max_chars,
        prompt_template=settings.prompt_template.read_text(encoding="utf-8"),
        remember_ttl_ms=settings.remember_ttl_ms,
        long_selection=settings.long_selection,
        fallback_cwd=str(settings.fallback_cwd),
    )


def run(
    argv: Sequence[str],
    stdin: Callable[[], str],
    policy: DeliveryPolicy,
    deps: DeliverDeps,
    notifier: Notifier,
) -> int:
    """Deliver the selection named by ``argv``; report problems by notification; return 0."""
    source = parse_argv(argv)
    match source:
        case BadUsage(message=message):
            logger.error(message)
            _notify(notifier, message)
            return 0
        case FromStdin():
            raw = stdin()
        case FromArgument(text=text):
            raw = text
        case _:
            assert_never(source)
    try:
        outcome = deliver_selection(raw, policy, deps)
    except Exception:
        logger.exception("delivery failed")
        _notify(notifier, "Could not deliver the selection; see the log.")
        return 0
    _report(outcome, policy, notifier)
    return 0


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.capture``."""
    notifier: Notifier | None = None
    try:
        from explain_selection.adapters import OsascriptNotifier, SubprocessRunner
        from explain_selection.entrypoints.deps import build_deliver_deps, current_process
        from explain_selection.entrypoints.settings import load_settings, resolve_plugin_root

        runner = SubprocessRunner()
        notifier = OsascriptNotifier(runner)
        environ = dict(os.environ)
        settings = load_settings(environ, resolve_plugin_root(environ, checkout_root()))
        configure_logging(settings.log_file, entrypoint_logger())
        policy = build_policy(settings)
        deps = build_deliver_deps(settings, environ, current_process(), runner)
        return run(sys.argv[1:], read_stdin, policy, deps, notifier)
    except Exception:
        logger.exception("capture could not start")
        if notifier is not None:
            _notify(notifier, "Explain selection could not start; see the log.")
        return 0


def _report(outcome: Outcome, policy: DeliveryPolicy, notifier: Notifier) -> None:
    match outcome:
        case Injected(target=target, reason=reason, chars=chars):
            status = target.session.status
            logger.info(
                "injected %d chars into pid %d (%s, %s)",
                chars,
                target.session.pid,
                reason.value,
                status.value,
            )
            if status is not SessionStatus.IDLE:
                _notify(
                    notifier,
                    f"Sent to {describe_target(target)}; it is {status.value} and will "
                    "answer when it is free.",
                )
            _report_truncation(outcome.truncated, outcome.original_chars, policy, notifier)
        case OpenedNewWindow(cwd=cwd, used_tempfile=used_tempfile, link_truncated=link_truncated):
            logger.info(
                "no live session; opened a new window in %s (tempfile=%s, link_truncated=%s)",
                cwd,
                used_tempfile,
                link_truncated,
            )
            _report_truncation(outcome.truncated, outcome.original_chars, policy, notifier)
            if link_truncated:
                _notify(
                    notifier,
                    "Selection shortened to fit the new-window link, which holds "
                    f"{DEEP_LINK_QUERY_LIMIT} characters ({outcome.chars} selected).",
                )
        case Cancelled():
            logger.info("session choice cancelled by the user")
        case NothingToSend():
            logger.info("empty selection; nothing sent")
            _notify(notifier, "Nothing selected.")
        case _:
            assert_never(outcome)


def _report_truncation(
    truncated: bool, original_chars: int, policy: DeliveryPolicy, notifier: Notifier
) -> None:
    if not truncated:
        return
    logger.info("selection truncated to %d of %d chars", policy.max_chars, original_chars)
    _notify(
        notifier,
        f"Selection truncated to {policy.max_chars} characters ({original_chars} selected).",
    )


def _notify(notifier: Notifier, message: str) -> None:
    try:
        notifier.notify(NOTIFICATION_TITLE, message)
    except Exception:
        logger.exception("notification failed")


__all__ = [
    "NOTIFICATION_TITLE",
    "USAGE",
    "BadUsage",
    "FromArgument",
    "FromStdin",
    "InputSource",
    "build_policy",
    "main",
    "parse_argv",
    "run",
]

if __name__ == "__main__":
    sys.exit(main())
