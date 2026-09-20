"""RegistryFiles persists one private JSON file per session, atomically."""

import json
import logging
import stat
from pathlib import Path

import pytest

from explain_selection.adapters import RegistryFiles
from explain_selection.domain import Pid
from tests.builders import entry


def test_save_then_read_roundtrips(tmp_path: Path) -> None:
    store = RegistryFiles(tmp_path / "sessions")
    saved = entry(2268544, tty="pts/2", tmux_pane="%7")
    store.save(saved)
    assert store.read_all() == (saved,)


def test_directory_and_file_have_private_modes(tmp_path: Path) -> None:
    directory = tmp_path / "sessions"
    RegistryFiles(directory).save(entry(10))
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / "10.json").stat().st_mode) == 0o600


def test_on_disk_keys_are_camel_case(tmp_path: Path) -> None:
    RegistryFiles(tmp_path).save(entry(10, tmux_pane="%7"))
    data: dict[str, object] = json.loads((tmp_path / "10.json").read_text(encoding="utf-8"))
    assert {"sessionId", "tmuxPane", "registeredAt", "pid", "token"} <= set(data)


def test_delete_removes_the_file(tmp_path: Path) -> None:
    store = RegistryFiles(tmp_path)
    store.save(entry(10))
    store.delete(Pid(10))
    assert store.read_all() == ()


def test_delete_missing_entry_is_silent(tmp_path: Path) -> None:
    RegistryFiles(tmp_path).delete(Pid(999))


def test_read_all_skips_invalid_files(tmp_path: Path) -> None:
    store = RegistryFiles(tmp_path)
    store.save(entry(10))
    (tmp_path / "20.json").write_text("{ not valid json", encoding="utf-8")
    assert [e.pid for e in store.read_all()] == [Pid(10)]


def test_read_all_skips_files_of_an_unknown_format_version(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = RegistryFiles(tmp_path)
    store.save(entry(10))
    store.save(entry(20))
    future = tmp_path / "20.json"
    data: dict[str, object] = json.loads(future.read_text(encoding="utf-8"))
    data["version"] = 2
    future.write_text(json.dumps(data), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="explain_selection"):
        assert [e.pid for e in store.read_all()] == [Pid(10)]
    assert "20.json" in caplog.text


def test_read_all_on_missing_directory_is_empty(tmp_path: Path) -> None:
    assert RegistryFiles(tmp_path / "does-not-exist").read_all() == ()


def test_save_leaves_no_temp_files(tmp_path: Path) -> None:
    RegistryFiles(tmp_path).save(entry(10))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["10.json"]
