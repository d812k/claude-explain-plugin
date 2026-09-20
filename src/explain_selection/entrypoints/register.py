"""SessionStart and CwdChanged hook: record this session's inbox address in the registry."""

import logging
import sys
from collections.abc import Mapping

from explain_selection.entrypoints.hooks import build_hook_context, hook_main, log_result
from explain_selection.services import RegisterDeps, register_session

logger = logging.getLogger(__name__)


def run(stdin_text: str, environ: Mapping[str, str], deps: RegisterDeps) -> int:
    """Register the session described by the hook input; the exit code is always 0."""
    ctx = build_hook_context(stdin_text, environ)
    log_result(logger, "register", register_session(ctx, deps))
    return 0


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.register``."""
    return hook_main(run)


__all__ = ["main", "run"]

if __name__ == "__main__":
    sys.exit(main())
