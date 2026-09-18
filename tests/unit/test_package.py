"""Smoke test: the package imports and exposes an explicit public interface."""

import explain_selection
from explain_selection.errors import ExplainSelectionError


def test_package_declares_public_interface() -> None:
    assert isinstance(explain_selection.__all__, list)


def test_base_error_is_an_exception() -> None:
    assert issubclass(ExplainSelectionError, Exception)
