"""The process probe answers liveness from signal 0 without touching other processes."""

import os

import pytest

from explain_selection.adapters import OsProcessProbe
from explain_selection.domain import Pid


def _raising(error: BaseException) -> "type[_Kill]":
    class Raising(_Kill):
        def __call__(self, pid: int, sig: int) -> None:
            super().__call__(pid, sig)
            raise error

    return Raising


class _Kill:
    """A stand-in for ``os.kill`` that records its calls and succeeds."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def __call__(self, pid: int, sig: int) -> None:
        self.calls.append((pid, sig))


def test_a_process_that_accepts_signal_zero_is_alive() -> None:
    kill = _Kill()
    assert OsProcessProbe(kill).is_alive(Pid(4242)) is True
    assert kill.calls == [(4242, 0)]


def test_a_missing_process_is_dead() -> None:
    kill = _raising(ProcessLookupError())()
    assert OsProcessProbe(kill).is_alive(Pid(4242)) is False


def test_a_process_we_may_not_signal_still_counts_as_alive() -> None:
    kill = _raising(PermissionError())()
    assert OsProcessProbe(kill).is_alive(Pid(1)) is True


def test_other_os_errors_propagate() -> None:
    kill = _raising(OSError("odd"))()
    with pytest.raises(OSError, match="odd"):
        OsProcessProbe(kill).is_alive(Pid(4242))


def test_the_default_probe_sees_this_very_process() -> None:
    assert OsProcessProbe().is_alive(Pid(os.getpid())) is True
