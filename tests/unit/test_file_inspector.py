"""LocalFileInspector answers from ``stat``; exercised only under tmp_path."""

import socket
from pathlib import Path

import pytest

from explain_selection.adapters import MISSING_FILE, LocalFileInspector
from explain_selection.domain import FileFacts


def test_a_missing_path_or_a_path_below_a_file_does_not_exist(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("", encoding="utf-8")
    inspector = LocalFileInspector()
    assert inspector.inspect(tmp_path / "absent") == MISSING_FILE
    assert inspector.inspect(tmp_path / "file" / "child") == MISSING_FILE
    assert MISSING_FILE.mode is None


def test_a_regular_file_reports_its_permission_bits_only(tmp_path: Path) -> None:
    target = tmp_path / "config.env"
    target.write_text("x", encoding="utf-8")
    target.chmod(0o640)
    assert LocalFileInspector().inspect(target) == FileFacts(
        exists=True, mode=0o640, is_dir=False, is_socket=False, is_executable=False
    )


def test_a_directory_and_an_executable_are_recognised(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    shim = home / "capture"
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    shim.chmod(0o700)
    inspector = LocalFileInspector()
    assert inspector.inspect(home) == FileFacts(
        exists=True, mode=0o700, is_dir=True, is_socket=False, is_executable=True
    )
    assert inspector.inspect(shim) == FileFacts(
        exists=True, mode=0o700, is_dir=False, is_socket=False, is_executable=True
    )


def test_read_text_returns_the_content_or_none_for_a_missing_file(tmp_path: Path) -> None:
    (tmp_path / "prompt.txt").write_text("Explain {text}\n", encoding="utf-8")
    inspector = LocalFileInspector()
    assert inspector.read_text(tmp_path / "prompt.txt") == "Explain {text}\n"
    assert inspector.read_text(tmp_path / "absent.txt") is None


def test_read_text_does_not_hide_other_errors(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        LocalFileInspector().read_text(tmp_path)


@pytest.mark.slow
def test_a_bound_unix_socket_is_a_socket(tmp_path: Path) -> None:
    path = tmp_path / "s.sock"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        facts = LocalFileInspector().inspect(path)
    assert (facts.exists, facts.is_socket, facts.is_dir) == (True, True, False)
