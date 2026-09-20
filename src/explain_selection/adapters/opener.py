"""``LinkOpener`` backed by ``open``: hands a ``claude-cli://`` deep link to macOS."""

from explain_selection.adapters.subprocess_runner import CommandRunner
from explain_selection.errors import SubprocessError


class OpenLinkOpener:
    """Opens a URL with the macOS ``open`` command."""

    def __init__(
        self, runner: CommandRunner, *, open_bin: str = "open", timeout_s: float = 5.0
    ) -> None:
        self._runner = runner
        self._open_bin = open_bin
        self._timeout_s = timeout_s

    def open(self, url: str) -> None:
        result = self._runner.run([self._open_bin, url], timeout=self._timeout_s)
        if result.returncode != 0:
            raise SubprocessError(f"open exited {result.returncode}")


__all__ = ["OpenLinkOpener"]
