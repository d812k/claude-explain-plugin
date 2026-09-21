"""LocalFileInspector: read-only ``stat`` questions and text reads for the doctor."""

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from explain_selection.domain import FileFacts

MISSING_FILE: Final[FileFacts] = FileFacts(
    exists=False, mode=None, is_dir=False, is_socket=False, is_executable=False
)


@dataclass(frozen=True, slots=True)
class LocalFileInspector:
    """The real inspector; every question is answered from one ``os.stat`` call."""

    def inspect(self, path: Path) -> FileFacts:
        try:
            result = os.stat(path)
        except (FileNotFoundError, NotADirectoryError):
            return MISSING_FILE
        mode = result.st_mode
        return FileFacts(
            exists=True,
            mode=stat.S_IMODE(mode),
            is_dir=stat.S_ISDIR(mode),
            is_socket=stat.S_ISSOCK(mode),
            is_executable=bool(mode & stat.S_IXUSR),
        )

    def read_text(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None


__all__ = ["MISSING_FILE", "LocalFileInspector"]
