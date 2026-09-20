"""TempFiles writes a selection to a unique private file and returns its path."""

import stat
from pathlib import Path

from explain_selection.adapters import TempFiles


def test_write_returns_a_path_holding_the_text(tmp_path: Path) -> None:
    written = Path(TempFiles(tmp_path / "spill").write("hello\nworld"))
    assert written.read_text(encoding="utf-8") == "hello\nworld"


def test_file_and_directory_are_private(tmp_path: Path) -> None:
    directory = tmp_path / "spill"
    written = Path(TempFiles(directory).write("x"))
    assert stat.S_IMODE(written.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_each_write_is_a_distinct_file(tmp_path: Path) -> None:
    files = TempFiles(tmp_path)
    assert files.write("one") != files.write("two")
