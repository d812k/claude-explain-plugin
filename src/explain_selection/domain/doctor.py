"""The doctor's verdicts: pure rules over facts that the services layer gathered.

Nothing here touches a file, a socket or a process. The services build a
:class:`DoctorFacts`, :func:`evaluate` turns it into an ordered tuple of :class:`Check`, and
the CLI prints them. Every ``warn`` or ``fail`` check names the exact fix.
"""

from typing import Final

from explain_selection.domain.doctor_checks import (
    INSTALL_FIX,
    PERMISSIONS_FIX,
    SERVICE_NAME,
    SHORTCUT_SETTINGS_PATH,
    UNREADABLE_PLUGIN_VERSION,
    Check,
    fail,
    ok,
    skip,
    unreadable,
    warn,
)
from explain_selection.domain.doctor_facts import (
    ClaudeFacts,
    DoctorFacts,
    FileFacts,
    MacFacts,
    RuntimeFacts,
    SessionFacts,
)
from explain_selection.domain.models import SessionKind

_PRIVATE_DIR_MODE: Final[int] = 0o700
_OTHER_USER_BITS: Final[int] = 0o077
_MS_PER_MINUTE: Final[int] = 60_000


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
        _settings_files(claude),
        _agents(claude),
        *(_session(session) for session in claude.sessions),
        _stale_entries(claude),
        _inbound_policy(claude),
        *_mac(facts.mac),
    )


def _home(runtime: RuntimeFacts) -> Check:
    home = runtime.home
    if not home.exists:
        return fail("home", "missing", INSTALL_FIX)
    if not home.readable:
        return unreadable("home", "home", "<home>")
    if not home.is_dir:
        return fail("home", "not a directory", INSTALL_FIX)
    if home.mode != _PRIVATE_DIR_MODE:
        return warn("home", f"mode {_octal(home.mode)}, expected 0700", INSTALL_FIX)
    return ok("home", "mode 0700")


def _venv(runtime: RuntimeFacts) -> Check:
    if not runtime.venv_python.exists:
        return fail("venv", "venv/bin/python missing", INSTALL_FIX)
    if not runtime.venv_python.readable:
        return unreadable("venv", "venv/bin/python", "<home>/venv/bin/python")
    return ok("venv", "venv/bin/python present")


def _version(runtime: RuntimeFacts) -> Check:
    plugin, installed = runtime.plugin_version, runtime.installed_version
    if plugin == UNREADABLE_PLUGIN_VERSION:
        return fail("version", "plugin.json unreadable", _unreadable_manifest_fix(runtime))
    bootstrap = f"run {runtime.plugin_root}/scripts/bootstrap.sh"
    if installed is None:
        return fail("version", f"nothing installed in the venv; plugin is {plugin}", bootstrap)
    if installed != plugin:
        return warn("version", f"installed {installed}, plugin is {plugin}", bootstrap)
    return ok("version", plugin)


def _unreadable_manifest_fix(runtime: RuntimeFacts) -> str:
    root = runtime.plugin_root
    if runtime.root_source == "shim":
        return (
            f"the recorded plugin root {root} is gone: reinstall the plugin with /plugin, "
            f"then {INSTALL_FIX}"
        )
    return f"the checkout at {root} is incomplete; reinstall it with /plugin"


def _shim(runtime: RuntimeFacts) -> Check:
    shim = runtime.shim
    if not shim.exists:
        return fail("shim", "capture missing", INSTALL_FIX)
    if not shim.readable:
        return unreadable("shim", "capture", "<home>/capture")
    if not shim.is_executable:
        return fail("shim", "capture is not executable", INSTALL_FIX)
    if runtime.shim_plugin_root is None:
        return fail("shim", "capture names no plugin root", INSTALL_FIX)
    if runtime.shim_plugin_root != runtime.plugin_root:
        detail = f"capture points at {runtime.shim_plugin_root}, plugin is at {runtime.plugin_root}"
        return warn("shim", detail, f"the plugin moved: {INSTALL_FIX}")
    detail = f"capture points at {runtime.plugin_root}"
    if runtime.root_source == "shim":
        detail += " (root taken from the shim; the plugin export was not set)"
    return ok("shim", detail)


def _config(runtime: RuntimeFacts) -> Check:
    if not runtime.config_present:
        return warn(
            "config", "config.env missing; defaults apply", f"{INSTALL_FIX} to write config.env"
        )
    return ok("config", "config.env present")


def _template(runtime: RuntimeFacts) -> Check:
    path = runtime.template_path
    if not runtime.template.exists:
        return fail("template", f"prompt template missing at {path}", INSTALL_FIX)
    if not runtime.template.readable:
        return unreadable("template", "prompt template", path)
    if not runtime.template_has_placeholder:
        fix = f"add {{text}} to {path}, or delete the file and rerun /explain-selection:install"
        return fail("template", f"{path} has no {{text}} placeholder", fix)
    return ok("template", f"{path} has the {{text}} placeholder")


def _plugin_enabled(claude: ClaudeFacts) -> Check:
    if not claude.plugin_enabled:
        fix = "enable the plugin with /plugin so the hooks register sessions"
        return warn("plugin-enabled", "not in enabledPlugins", fix)
    return ok("plugin-enabled", "listed in enabledPlugins")


def _settings_files(claude: ClaudeFacts) -> Check:
    if claude.unreadable_settings:
        files = ", ".join(claude.unreadable_settings)
        return warn("settings-files", f"skipped {files}", f"fix the JSON in {files}")
    return ok("settings-files", "all readable")


def _agents(claude: ClaudeFacts) -> Check:
    if claude.agents_error is not None:
        fix = "check that claude is on PATH and claude agents --json works"
        return fail("agents", claude.agents_error or "claude agents --json failed", fix)
    return ok("agents", f"{len(claude.sessions)} live sessions")


def _session(session: SessionFacts) -> Check:
    name = f"session {session.pid}"
    detail = _session_detail(session)
    if not session.registered:
        if session.kind is SessionKind.INTERACTIVE:
            fix = (
                "restart this session with the plugin enabled; token-less messages are held by "
                "sessions that bypass permission prompts"
            )
            return warn(name, detail, fix)
        return ok(name, detail)
    socket = session.socket
    if socket is not None and socket.exists and not socket.readable:
        return fail(name, detail, f"{PERMISSIONS_FIX} the inbox socket")
    if socket is None or not _socket_ok(socket):
        return fail(name, detail, "the session's inbox socket is gone; restart it")
    if socket.mode is not None and socket.mode & _OTHER_USER_BITS:
        fix = "socket is accessible to other users; restart the session so it is recreated"
        return warn(name, detail, fix)
    return ok(name, detail)


def _session_detail(session: SessionFacts) -> str:
    parts = [
        session.status.value,
        session.kind.value,
        "registered" if session.registered else "unregistered",
    ]
    if session.tmux is not None:
        parts.append(f"tmux {session.tmux}")
    if session.socket is not None:
        parts.append(_socket_word(session.socket))
    parts.append(f"up {session.age_ms // _MS_PER_MINUTE}m")
    return " ".join(parts)


def _socket_word(socket: FileFacts) -> str:
    if _socket_ok(socket):
        return "socket ok"
    if socket.exists and not socket.readable:
        return "socket unreadable"
    return "socket missing"


def _socket_ok(socket: FileFacts) -> bool:
    return socket.exists and socket.is_socket


def _stale_entries(claude: ClaudeFacts) -> Check:
    count = claude.stale_entries
    if count > 0:
        fix = "capture prunes them; or delete <home>/sessions/<pid>.json for dead pids"
        noun = "entry" if count == 1 else "entries"
        return warn("stale-entries", f"{count} {noun} for dead sessions", fix)
    return ok("stale-entries", "none")


def _inbound_policy(claude: ClaudeFacts) -> Check:
    policy = claude.cross_session_inbound
    if policy == "refuse":
        fix = "set crossSessionInbound to accept in ~/.claude/settings.json"
        return fail("inbound-policy", "crossSessionInbound is refuse", fix)
    if policy == "hold":
        fix = "set crossSessionInbound to accept, or approve each message"
        return warn("inbound-policy", "crossSessionInbound is hold", fix)
    if policy is None:
        return ok("inbound-policy", "default: token-bearing messages are accepted")
    return ok("inbound-policy", policy)


def _mac(mac: MacFacts | None) -> tuple[Check, Check, Check]:
    if mac is None:
        return skip("services-bundle"), skip("shortcut"), skip("osascript")
    return _bundle(mac), _shortcut(mac), _osascript(mac)


def _bundle(mac: MacFacts) -> Check:
    bundle = f"{SERVICE_NAME}.workflow"
    if not mac.bundle.exists:
        return fail("services-bundle", f"{bundle} missing", INSTALL_FIX)
    if not mac.bundle.readable:
        return unreadable("services-bundle", bundle, f"~/Library/Services/{bundle}")
    return ok("services-bundle", f"{bundle} installed")


def _shortcut(mac: MacFacts) -> Check:
    status = mac.shortcut_status
    if status is None:
        return fail("shortcut", "could not read the Services status", SHORTCUT_SETTINGS_PATH)
    if SERVICE_NAME not in status:
        return fail("shortcut", f"{SERVICE_NAME} has no Services shortcut", SHORTCUT_SETTINGS_PATH)
    return ok("shortcut", f"{SERVICE_NAME} is in the Services menu")


def _osascript(mac: MacFacts) -> Check:
    if not mac.osascript_found:
        fix = "osascript ships with macOS; check PATH includes /usr/bin"
        return fail("osascript", "not found on PATH", fix)
    return ok("osascript", "found")


def _octal(mode: int | None) -> str:
    return "unknown" if mode is None else f"{mode:04o}"


__all__ = ["evaluate"]
