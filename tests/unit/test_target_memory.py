"""FileTargetMemory remembers the last explicit pick across hotkey presses."""

import stat
from pathlib import Path

from explain_selection.adapters import FileTargetMemory
from explain_selection.domain import Pid, RememberedTarget


def test_save_then_load_roundtrips(tmp_path: Path) -> None:
    memory = FileTargetMemory(tmp_path / "state" / "last-target.json")
    memory.save(RememberedTarget(Pid(42), 1_700_000_000_000))
    assert memory.load() == RememberedTarget(Pid(42), 1_700_000_000_000)


def test_missing_file_loads_none(tmp_path: Path) -> None:
    assert FileTargetMemory(tmp_path / "absent.json").load() is None


def test_invalid_file_loads_none(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json at all", encoding="utf-8")
    assert FileTargetMemory(path).load() is None


def test_parent_directory_is_private(tmp_path: Path) -> None:
    parent = tmp_path / "state"
    FileTargetMemory(parent / "last.json").save(RememberedTarget(Pid(1), 1))
    assert stat.S_IMODE(parent.stat().st_mode) == 0o700
