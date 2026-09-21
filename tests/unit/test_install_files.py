"""LocalInstallFiles: the real install file layer, exercised only under tmp_path."""

import stat
from pathlib import Path

import pytest

from explain_selection.adapters import LocalInstallFiles
from explain_selection.errors import InstallError


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_ensure_private_dir_creates_missing_parents_with_mode_0700(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    LocalInstallFiles().ensure_private_dir(target)
    assert target.is_dir()
    assert _mode(target) == 0o700


def test_ensure_private_dir_tightens_an_existing_directory_and_keeps_its_files(
    tmp_path: Path,
) -> None:
    target = tmp_path / "home"
    target.mkdir(mode=0o755)
    (target / "keep").write_text("x", encoding="utf-8")
    LocalInstallFiles().ensure_private_dir(target)
    assert _mode(target) == 0o700
    assert (target / "keep").read_text(encoding="utf-8") == "x"


def test_ensure_private_dir_over_a_file_is_an_install_error(tmp_path: Path) -> None:
    (tmp_path / "file").write_text("", encoding="utf-8")
    with pytest.raises(InstallError, match="could not create"):
        LocalInstallFiles().ensure_private_dir(tmp_path / "file")


def test_exists_sees_files_and_directories_but_not_absent_paths(tmp_path: Path) -> None:
    (tmp_path / "f").write_text("", encoding="utf-8")
    files = LocalInstallFiles()
    assert files.exists(tmp_path / "f")
    assert files.exists(tmp_path)
    assert not files.exists(tmp_path / "missing")


def test_write_private_file_writes_the_content_and_sets_the_mode(tmp_path: Path) -> None:
    target = tmp_path / "capture"
    LocalInstallFiles().write_private_file(target, "#!/bin/sh\n", 0o700)
    assert target.read_text(encoding="utf-8") == "#!/bin/sh\n"
    assert _mode(target) == 0o700


def test_write_private_file_overwrites_content_and_mode(tmp_path: Path) -> None:
    target = tmp_path / "config.env"
    files = LocalInstallFiles()
    files.write_private_file(target, "old\n", 0o700)
    files.write_private_file(target, "new\n", 0o600)
    assert target.read_text(encoding="utf-8") == "new\n"
    assert _mode(target) == 0o600


def test_write_private_file_into_a_missing_directory_is_an_install_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(InstallError, match="could not write"):
        LocalInstallFiles().write_private_file(tmp_path / "missing" / "f", "x", 0o600)


def test_copy_file_copies_the_contents(tmp_path: Path) -> None:
    src = tmp_path / "template.txt"
    src.write_text("Explain {text}\n", encoding="utf-8")
    LocalInstallFiles().copy_file(src, tmp_path / "copy.txt")
    assert (tmp_path / "copy.txt").read_text(encoding="utf-8") == "Explain {text}\n"


def test_copy_file_of_a_missing_source_is_an_install_error(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="could not copy"):
        LocalInstallFiles().copy_file(tmp_path / "missing", tmp_path / "copy")


def _bundle(root: Path, name: str, plist: str) -> Path:
    bundle = root / name
    (bundle / "Contents").mkdir(parents=True)
    (bundle / "Contents" / "Info.plist").write_text(plist, encoding="utf-8")
    return bundle


def test_replace_tree_copies_the_bundle_and_creates_the_missing_parent(tmp_path: Path) -> None:
    src = _bundle(tmp_path / "assets", "X.workflow", "plist")
    dst = tmp_path / "Library" / "Services" / "X.workflow"
    LocalInstallFiles().replace_tree(src, dst)
    assert (dst / "Contents" / "Info.plist").read_text(encoding="utf-8") == "plist"


def test_replace_tree_removes_what_was_installed_before(tmp_path: Path) -> None:
    src = _bundle(tmp_path / "assets", "X.workflow", "new")
    dst = _bundle(tmp_path / "Services", "X.workflow", "old")
    (dst / "Contents" / "stale").write_text("", encoding="utf-8")
    LocalInstallFiles().replace_tree(src, dst)
    assert (dst / "Contents" / "Info.plist").read_text(encoding="utf-8") == "new"
    assert not (dst / "Contents" / "stale").exists()


def test_replace_tree_of_a_missing_source_is_an_install_error(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match="could not install"):
        LocalInstallFiles().replace_tree(tmp_path / "missing", tmp_path / "dst")
