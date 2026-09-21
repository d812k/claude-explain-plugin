"""The new-window fallback end to end: the capture entrypoint as a subprocess.

Fake ``claude``, ``open`` and ``osascript`` scripts sit first on ``PATH``; ``claude`` reports
no live session, the other two record their arguments. Runs only under make test-all.
"""

import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_FAKE_CLAUDE = """#!/bin/sh
if [ "$1" = "agents" ] && [ "$2" = "--json" ]; then
  printf '[]'
fi
exit 0
"""

_FAKE_RECORDER = """#!/bin/sh
printf '%s\\n' "$@" >> '{record}'
exit 0
"""


def _write_script(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o700)


def _install_fake_binaries(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return the fake bin dir and the files where ``open`` and ``osascript`` record argv."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    open_record = tmp_path / "open.args"
    osascript_record = tmp_path / "osascript.args"
    _write_script(bin_dir / "claude", _FAKE_CLAUDE)
    _write_script(bin_dir / "open", _FAKE_RECORDER.format(record=open_record))
    _write_script(bin_dir / "osascript", _FAKE_RECORDER.format(record=osascript_record))
    return bin_dir, open_record, osascript_record


def _run_capture(
    tmp_path: Path, bin_dir: Path, text: str, extra_env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "EXPLAIN_SELECTION_HOME": str(tmp_path / "home"),
        "EXPLAIN_SELECTION_PLUGIN_ROOT": str(REPO_ROOT),
        **extra_env,
    }
    return subprocess.run(
        [sys.executable, "-m", "explain_selection.entrypoints.capture", "--text", text],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


@pytest.mark.integration
def test_no_live_session_opens_a_deep_link_and_logs_privately(tmp_path: Path) -> None:
    bin_dir, open_record, _ = _install_fake_binaries(tmp_path)

    result = _run_capture(tmp_path, bin_dir, "hello world", {})

    assert result.returncode == 0
    assert result.stdout == ""
    url = open_record.read_text().rstrip("\n")
    assert url.startswith("claude-cli://open?cwd=")
    assert quote("/explain-selection:explain hello world", safe="") in url
    log_file = tmp_path / "home" / "explain-selection.log"
    assert log_file.is_file()
    assert stat.S_IMODE(log_file.stat().st_mode) == 0o600


@pytest.mark.integration
def test_capped_selection_reports_the_truncation_through_osascript(tmp_path: Path) -> None:
    bin_dir, _, osascript_record = _install_fake_binaries(tmp_path)

    result = _run_capture(tmp_path, bin_dir, "a" * 6000, {"EXPLAIN_SELECTION_MAX_CHARS": "1000"})

    assert result.returncode == 0
    assert result.stdout == ""
    assert "truncated" in osascript_record.read_text()
