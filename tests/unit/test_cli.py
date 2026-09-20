"""The explain-selection command line prints its version and rejects anything else."""

import io

import pytest

from explain_selection.entrypoints.cli import package_version, run


def test_version_prints_the_package_version() -> None:
    out = io.StringIO()
    assert run(["version"], out) == 0
    assert out.getvalue() == f"{package_version()}\n"


def test_version_is_a_dotted_number_when_installed() -> None:
    assert package_version().count(".") >= 2


def test_a_subcommand_is_required() -> None:
    with pytest.raises(SystemExit):
        run([], io.StringIO())
