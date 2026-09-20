"""SubprocessRunner against real commands. Runs only under make test-all."""

import pytest

from explain_selection.adapters import SubprocessRunner
from explain_selection.errors import SubprocessError


@pytest.mark.integration
def test_runs_a_real_command() -> None:
    result = SubprocessRunner().run(["printf", "hello"], timeout=5)
    assert result.returncode == 0
    assert result.stdout == "hello"


@pytest.mark.integration
def test_missing_command_raises_subprocess_error_naming_only_the_executable() -> None:
    with pytest.raises(SubprocessError, match=r"^explain-selection-no-such-binary-xyz not found$"):
        SubprocessRunner().run(
            ["explain-selection-no-such-binary-xyz", "claude-cli://open?q=secret"], timeout=5
        )


@pytest.mark.integration
def test_timeout_raises_subprocess_error_without_the_arguments() -> None:
    with pytest.raises(SubprocessError, match=r"^sleep timed out after 0\.2 s$"):
        SubprocessRunner().run(["sleep", "5"], timeout=0.2)
