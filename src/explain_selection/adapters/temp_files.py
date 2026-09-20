"""``TempFileWriter``: spill an oversized selection to a private file for the mode A fallback."""

import os
import tempfile
from pathlib import Path


class TempFiles:
    """Writes selections to unique files under a mode 0700 directory."""

    def __init__(self, directory: Path, *, prefix: str = "selection-") -> None:
        self._directory = directory
        self._prefix = prefix

    def write(self, text: str) -> str:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)
        fd, path = tempfile.mkstemp(dir=self._directory, prefix=self._prefix, suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path


__all__ = ["TempFiles"]
