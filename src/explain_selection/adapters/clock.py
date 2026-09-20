"""Wall-clock time for the composition roots; the core only ever sees the Clock protocol."""

import time
from collections.abc import Callable

_MS_PER_S = 1000


class SystemClock:
    """Epoch milliseconds from a seconds-returning time function, :func:`time.time` by default."""

    def __init__(self, time_fn: Callable[[], float] = time.time) -> None:
        self._time_fn = time_fn

    def now_ms(self) -> int:
        return int(self._time_fn() * _MS_PER_S)


__all__ = ["SystemClock"]
