"""Process liveness via signal 0; the core only ever sees the ProcessProbe protocol."""

import os
from collections.abc import Callable

from explain_selection.domain import Pid


class OsProcessProbe:
    """Asks the kernel whether a pid exists by sending it signal 0 (:func:`os.kill` by default)."""

    def __init__(self, kill: Callable[[int, int], None] = os.kill) -> None:
        self._kill = kill

    def is_alive(self, pid: Pid) -> bool:
        """``False`` only when the kernel says there is no such process.

        ``PermissionError`` means the process exists but belongs to someone else, so it is
        alive; any other ``OSError`` propagates rather than being guessed at.
        """
        try:
            self._kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


__all__ = ["OsProcessProbe"]
