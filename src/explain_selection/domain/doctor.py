"""The doctor's verdicts: pure rules over facts that the services layer gathered.

Nothing here touches a file, a socket or a process. The services build a
:class:`DoctorFacts`, :func:`evaluate` turns it into an ordered tuple of :class:`Check`, and
the CLI prints them. Every ``warn`` or ``fail`` check names the exact fix.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from explain_selection.domain.doctor_facts import (
    ClaudeFacts,
    DoctorFacts,
    FileFacts,
    MacFacts,
    RuntimeFacts,
    SessionFacts,
)
from explain_selection.domain.models import SessionKind

type CheckStatus = Literal["ok", "warn", "fail", "skip"]

UNREADABLE_PLUGIN_VERSION: Final[str] = ""
INSTALL_FIX: Final[str] = "run /explain-selection:install"
MACOS_ONLY: Final[str] = "macOS only"
_SERVICE_NAME: Final[str] = "Explain selection"
_PRIVATE_DIR_MODE: Final[int] = 0o700
_OTHER_USER_BITS: Final[int] = 0o077
_MS_PER_MINUTE: Final[int] = 60_000
_SHORTCUT_FIX: Final[str] = (
    f"System Settings > Keyboard > Keyboard Shortcuts > Services > Text > {_SERVICE_NAME}"
)


@dataclass(frozen=True, slots=True)
class Check:
    """One verdict; ``fix`` is set exactly when the status is ``warn`` or ``fail``."""

    name: str
    status: CheckStatus
    detail: str
    fix: str | None


def evaluate(facts: DoctorFacts) -> tuple[Check, ...]:
    """Every check in display order; one ``session <pid>`` check per live session."""
    runtime, claude = facts.runtime, facts.claude
    return (
        _home(runtime),
        _venv(runtime),
        _version(runtime),
        _shim(runtime),
        _config(runtime),
        _template(runtime),
        _plugin_enabled(claude),
        _agents(claude),
        *(_session(session) for session in claude.sessions),
        _stale_entries(claude),
        _inbound_policy(claude),
        *_mac(facts.mac),
    )


def checks_ok(checks: Iterable[Check]) -> bool:
    """``True`` unless some check failed; warnings and skips are fine."""
    return all(check.status != "fail" for check in checks)


def _ok(name: str, detail: str) -> Check:
    return Check(name=name, status="ok", detail=detail, fix=None)


def _warn(name: str, detail: str, fix: str) -> Check:
    return Check(name=name, status="warn", detail=detail, fix=fix)


def _fail(name: str, detail: str, fix: str) -> Check:
    return Check(name=name, status="fail", detail=detail, fix=fix)


def _skip(name: str) -> Check:
    return Check(name=name, status="skip", detail=MACOS_ONLY, fix=None)


def _home(runtime: RuntimeFacts) -> Check:
    home = runtime.home
    if not home.exists:
        return _fail("home", "missing", INSTALL_FIX)
    if not home.is_dir:
        return _fail("home", "not a directory", INSTALL_FIX)
    if home.mode != _PRIVATE_DIR_MODE:
        return _warn("home", f"mode {_octal(home.mode)}, expected 0700", INSTALL_FIX)
    return _ok("home", "mode 0700")


def _venv(runtime: RuntimeFacts) -> Check:
    if not runtime.venv_python.exists:
        return _fail("venv", "venv/bin/python missing", INSTALL_FIX)
    return _ok("venv", "venv/bin/python present")


def _version(runtime: RuntimeFacts) -> Check:
    plugin, installed = runtime.plugin_version, runtime.installed_version
    if plugin == UNREADABLE_PLUGIN_VERSION:
        fix = f"the checkout at {runtime.plugin_root} is incomplete; reinstall it with /plugin"
        return _fail("version", "plugin.json unreadable", fix)
    bootstrap = f"run {runtime.plugin_root}/scripts/bootstrap.sh"
    if installed is None:
        return _fail("version", f"nothing installed in the venv; plugin is {plugin}", bootstrap)
    if installed != plugin:
        return _warn("version", f"installed {installed}, plugin is {plugin}", bootstrap)
    return _ok("version", plugin)


def _shim(runtime: RuntimeFacts) -> Check:
    shim = runtime.shim
    if not shim.exists:
        return _fail("shim", "capture missing", INSTALL_FIX)
    if not shim.is_executable:
        return _fail("shim", "capture is not executable", INSTALL_FIX)
    if runtime.shim_plugin_root is None:
        return _fail("shim", "capture names no plugin root", INSTALL_FIX)
    if runtime.shim_plugin_root != runtime.plugin_root:
        detail = f"capture points at {runtime.shim_plugin_root}, plugin is at {runtime.plugin_root}"
        return _warn("shim", detail, f"the plugin moved: {INSTALL_FIX}")
    return _ok("shim", f"capture points at {runtime.plugin_root}")


def _config(runtime: RuntimeFacts) -> Check:
    if not runtime.config_present:
        return _warn(
            "config", "config.env missing; defaults apply", f"{INSTALL_FIX} to write config.env"
        )
    return _ok("config", "config.env present")


def _template(runtime: RuntimeFacts) -> Check:
    fix = f"restore it from templates/explain-prompt.txt: {INSTALL_FIX}"
    if not runtime.template_present:
        return _fail("template", "prompt template missing", fix)
    if not runtime.template_has_placeholder:
        return _fail("template", "prompt template has no {text} placeholder", fix)
    return _ok("template", "prompt template has the {text} placeholder")


def _plugin_enabled(claude: ClaudeFacts) -> Check:
    if not claude.plugin_enabled:
        fix = "enable the plugin with /plugin so the hooks register sessions"
        return _warn("plugin-enabled", "not in enabledPlugins", fix)
    return _ok("plugin-enabled", "listed in enabledPlugins")


def _agents(claude: ClaudeFacts) -> Check:
    if claude.agents_error is not None:
        fix = "check that claude is on PATH and claude agents --json works"
        return _fail("agents", claude.agents_error or "claude agents --json failed", fix)
    return _ok("agents", f"{len(claude.sessions)} live sessions")


def _session(session: SessionFacts) -> Check:
    name = f"session {session.pid}"
    detail = _session_detail(session)
    if not session.registered:
        if session.kind is SessionKind.INTERACTIVE:
            fix = (
                "restart this session with the plugin enabled; token-less messages are held by "
                "sessions that bypass permission prompts"
            )
            return _warn(name, detail, fix)
        return _ok(name, detail)
    socket = session.socket
    if socket is None or not _socket_ok(socket):
        return _fail(name, detail, "the session's inbox socket is gone; restart it")
    if socket.mode is not None and socket.mode & _OTHER_USER_BITS:
        fix = "socket is accessible to other users; restart the session so it is recreated"
        return _warn(name, detail, fix)
    return _ok(name, detail)


def _session_detail(session: SessionFacts) -> str:
    parts = [
        session.status.value,
        session.kind.value,
        "registered" if session.registered else "unregistered",
    ]
    if session.tmux is not None:
        parts.append(f"tmux {session.tmux}")
    if session.socket is not None:
        parts.append("socket ok" if _socket_ok(session.socket) else "socket missing")
    parts.append(f"up {session.age_ms // _MS_PER_MINUTE}m")
    return " ".join(parts)


def _socket_ok(socket: FileFacts) -> bool:
    return socket.exists and socket.is_socket


def _stale_entries(claude: ClaudeFacts) -> Check:
    count = claude.stale_entries
    if count > 0:
        fix = "capture prunes them; or delete <home>/sessions/<pid>.json for dead pids"
        noun = "entry" if count == 1 else "entries"
        return _warn("stale-entries", f"{count} {noun} for dead sessions", fix)
    return _ok("stale-entries", "none")


def _inbound_policy(claude: ClaudeFacts) -> Check:
    policy = claude.cross_session_inbound
    if policy == "refuse":
        fix = "set crossSessionInbound to accept in ~/.claude/settings.json"
        return _fail("inbound-policy", "crossSessionInbound is refuse", fix)
    if policy == "hold":
        fix = "set crossSessionInbound to accept, or approve each message"
        return _warn("inbound-policy", "crossSessionInbound is hold", fix)
    if policy is None:
        return _ok("inbound-policy", "default: token-bearing messages are accepted")
    return _ok("inbound-policy", policy)


def _mac(mac: MacFacts | None) -> tuple[Check, Check, Check]:
    if mac is None:
        return _skip("services-bundle"), _skip("shortcut"), _skip("osascript")
    return _bundle(mac), _shortcut(mac), _osascript(mac)


def _bundle(mac: MacFacts) -> Check:
    if not mac.bundle.exists:
        return _fail("services-bundle", f"{_SERVICE_NAME}.workflow missing", INSTALL_FIX)
    return _ok("services-bundle", f"{_SERVICE_NAME}.workflow installed")


def _shortcut(mac: MacFacts) -> Check:
    status = mac.shortcut_status
    if status is None:
        return _fail("shortcut", "could not read the Services status", _SHORTCUT_FIX)
    if _SERVICE_NAME not in status:
        return _fail("shortcut", f"{_SERVICE_NAME} has no Services shortcut", _SHORTCUT_FIX)
    return _ok("shortcut", f"{_SERVICE_NAME} is in the Services menu")


def _osascript(mac: MacFacts) -> Check:
    if not mac.osascript_found:
        fix = "osascript ships with macOS; check PATH includes /usr/bin"
        return _fail("osascript", "not found on PATH", fix)
    return _ok("osascript", "found")


def _octal(mode: int | None) -> str:
    return "unknown" if mode is None else f"{mode:04o}"


__all__ = [
    "INSTALL_FIX",
    "MACOS_ONLY",
    "UNREADABLE_PLUGIN_VERSION",
    "Check",
    "CheckStatus",
    "checks_ok",
    "evaluate",
]
