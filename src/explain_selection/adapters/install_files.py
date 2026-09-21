"""``InstallFiles`` on the local filesystem: pathlib, shutil and chmod, with typed errors."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from explain_selection.errors import InstallError

_PRIVATE_DIR_MODE: Final[int] = 0o700


def _reason(exc: OSError) -> str:
    return exc.strerror or str(exc)


@dataclass(frozen=True, slots=True)
class LocalInstallFiles:
    """The real file layer for install; every ``OSError`` becomes an :class:`InstallError`."""

    def ensure_private_dir(self, path: Path) -> None:
        try:
            path.mkdir(mode=_PRIVATE_DIR_MODE, parents=True, exist_ok=True)
            os.chmod(path, _PRIVATE_DIR_MODE)
        except OSError as exc:
            raise InstallError(f"could not create {path}: {_reason(exc)}") from exc

    def exists(self, path: Path) -> bool:
        return path.exists()

    def write_private_file(self, path: Path, content: str, mode: int) -> None:
        try:
            path.write_text(content, encoding="utf-8")
            os.chmod(path, mode)
        except OSError as exc:
            raise InstallError(f"could not write {path}: {_reason(exc)}") from exc

    def copy_file(self, src: Path, dst: Path) -> None:
        try:
            shutil.copyfile(src, dst)
        except OSError as exc:
            raise InstallError(f"could not copy {src} to {dst}: {_reason(exc)}") from exc

    def replace_tree(self, src: Path, dst: Path) -> None:
        try:
            if dst.is_dir():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)
        except OSError as exc:
            raise InstallError(f"could not install {src} to {dst}: {_reason(exc)}") from exc


__all__ = ["LocalInstallFiles"]
