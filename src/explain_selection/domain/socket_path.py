"""Pure resolution of a session's inbox socket path from its pid, and back."""

from collections.abc import Mapping
from typing import Final

from explain_selection.domain.models import Pid

SOCKET_DIR_NAME: Final[str] = "cc-socks"
SOCKET_SUFFIX: Final[str] = ".sock"
MAX_SOCKET_PATH_BYTES: Final[int] = 103


def candidate_socket_paths(pid: Pid, env: Mapping[str, str], uid: int) -> tuple[str, ...]:
    """Return the inbox socket paths Claude Code may use for ``pid``, most likely first."""
    runtime_dir = env.get("XDG_RUNTIME_DIR") or "/tmp"
    primary = f"{runtime_dir}/{SOCKET_DIR_NAME}/{pid}{SOCKET_SUFFIX}"
    fallback = f"/tmp/{SOCKET_DIR_NAME}-{uid}/{pid}{SOCKET_SUFFIX}"
    if len(primary.encode()) > MAX_SOCKET_PATH_BYTES:
        return (fallback,)
    return (primary, fallback)


def pid_from_socket_path(path: str) -> Pid | None:
    """Extract the Claude Code pid from an inbox socket path, or ``None`` if it is not one."""
    name = path.rsplit("/", 1)[-1]
    if not name.endswith(SOCKET_SUFFIX):
        return None
    stem = name.removesuffix(SOCKET_SUFFIX)
    if not stem.isdigit():
        return None
    return Pid(int(stem))


__all__ = [
    "MAX_SOCKET_PATH_BYTES",
    "SOCKET_DIR_NAME",
    "SOCKET_SUFFIX",
    "candidate_socket_paths",
    "pid_from_socket_path",
]
