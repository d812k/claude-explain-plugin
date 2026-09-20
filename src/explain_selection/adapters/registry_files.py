"""``RegistryStore`` backed by one JSON file per session under a private directory.

The directory is mode 0700 and each file mode 0600, written atomically (temp file in the same
directory, then rename). Files hold the per-session inbox token, so they are never committed
and never logged; readers skip files that fail to validate, logging only the filename.
"""

import contextlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from explain_selection.domain import (
    InboxToken,
    Pid,
    RegistryEntry,
    SessionId,
)
from explain_selection.errors import RegistryError

logger = logging.getLogger(__name__)


class _RegistryFileModel(BaseModel):
    """The on-disk shape (format version 1); camelCase keys, unknown keys ignored.

    Any other ``version`` fails validation, so a file from a newer format is skipped and
    logged like any invalid file rather than half-read.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    version: Literal[1] = 1
    session_id: str | None = Field(default=None, alias="sessionId")
    pid: int
    cwd: str
    tty: str | None = None
    name: str | None = None
    socket: str
    token: str
    tmux: str | None = None
    tmux_pane: str | None = Field(default=None, alias="tmuxPane")
    registered_at_ms: int = Field(alias="registeredAt")


def _dump(entry: RegistryEntry) -> str:
    model = _RegistryFileModel.model_validate(
        {
            "version": entry.version,
            "sessionId": entry.session_id,
            "pid": int(entry.pid),
            "cwd": entry.cwd,
            "tty": entry.tty,
            "name": entry.name,
            "socket": entry.socket,
            "token": str(entry.token),
            "tmux": entry.tmux,
            "tmuxPane": entry.tmux_pane,
            "registeredAt": entry.registered_at_ms,
        }
    )
    return model.model_dump_json(by_alias=True)


def _load(raw: str) -> RegistryEntry:
    model = _RegistryFileModel.model_validate_json(raw)
    return RegistryEntry(
        session_id=SessionId(model.session_id) if model.session_id else None,
        pid=Pid(model.pid),
        cwd=model.cwd,
        tty=model.tty,
        name=model.name,
        socket=model.socket,
        token=InboxToken(model.token),
        tmux=model.tmux,
        tmux_pane=model.tmux_pane,
        registered_at_ms=model.registered_at_ms,
        version=model.version,
    )


class RegistryFiles:
    """Persists registry entries as ``<pid>.json`` files under ``directory``."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, entry: RegistryEntry) -> None:
        self._ensure_dir()
        payload = _dump(entry).encode()
        path = self._directory / f"{int(entry.pid)}.json"
        fd, tmp_name = tempfile.mkstemp(
            dir=self._directory, prefix=f".{int(entry.pid)}.", suffix=".tmp"
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp, path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                tmp.unlink()
            raise RegistryError(f"could not write registry entry for pid {int(entry.pid)}") from exc

    def delete(self, pid: Pid) -> None:
        with contextlib.suppress(FileNotFoundError):
            (self._directory / f"{int(pid)}.json").unlink()

    def read_all(self) -> tuple[RegistryEntry, ...]:
        if not self._directory.is_dir():
            return ()
        entries: list[RegistryEntry] = []
        for path in sorted(self._directory.glob("*.json")):
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                logger.warning("could not read registry file %s", path.name)
                continue
            try:
                entries.append(_load(raw))
            except ValidationError:
                logger.warning("skipping invalid registry file %s", path.name)
                continue
        return tuple(entries)

    def _ensure_dir(self) -> None:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)


__all__ = ["RegistryFiles"]
