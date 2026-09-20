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
def test_missing_command_raises_subprocess_error() -> None:
    with pytest.raises(SubprocessError):
        SubprocessRunner().run(["explain-selection-no-such-binary-xyz"], timeout=5)
