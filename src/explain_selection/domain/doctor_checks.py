"""The doctor's vocabulary: the :class:`Check` verdict, its constructors and shared wording.

Kept apart from the rules in :mod:`explain_selection.domain.doctor` so each stays small.
The wording constants are the single definition the services layer reuses in the
installer's own messages.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

type CheckStatus = Literal["ok", "warn", "fail", "skip"]

UNREADABLE_PLUGIN_VERSION: Final[str] = ""
INSTALL_FIX: Final[str] = "run /explain-selection:install"
MACOS_ONLY: Final[str] = "macOS only"
SERVICE_NAME: Final[str] = "Explain selection"
SHORTCUT_SETTINGS_PATH: Final[str] = (
    f"System Settings > Keyboard > Keyboard Shortcuts > Services > Text > {SERVICE_NAME}"
)
PERMISSIONS_FIX: Final[str] = "check ownership and permissions of"


@dataclass(frozen=True, slots=True)
class Check:
    """One verdict; ``fix`` is set exactly when the status is ``warn`` or ``fail``."""

    name: str
    status: CheckStatus
    detail: str
    fix: str | None


def checks_ok(checks: Iterable[Check]) -> bool:
    """``True`` unless some check failed; warnings and skips are fine."""
    return all(check.status != "fail" for check in checks)


def ok(name: str, detail: str) -> Check:
    """A passing check."""
    return Check(name=name, status="ok", detail=detail, fix=None)


def warn(name: str, detail: str, fix: str) -> Check:
    """A check that passes with a caveat the user should act on."""
    return Check(name=name, status="warn", detail=detail, fix=fix)


def fail(name: str, detail: str, fix: str) -> Check:
    """A failing check; ``checks_ok`` is false when any is present."""
    return Check(name=name, status="fail", detail=detail, fix=fix)


def skip(name: str) -> Check:
    """A check that does not apply off macOS."""
    return Check(name=name, status="skip", detail=MACOS_ONLY, fix=None)


def unreadable(name: str, what: str, path: str) -> Check:
    """The failing check for a file that exists but cannot be read."""
    return fail(name, f"{what} exists but cannot be read", f"{PERMISSIONS_FIX} {path}")


__all__ = [
    "INSTALL_FIX",
    "MACOS_ONLY",
    "PERMISSIONS_FIX",
    "SERVICE_NAME",
    "SHORTCUT_SETTINGS_PATH",
    "UNREADABLE_PLUGIN_VERSION",
    "Check",
    "CheckStatus",
    "checks_ok",
    "fail",
    "ok",
    "skip",
    "unreadable",
    "warn",
]
