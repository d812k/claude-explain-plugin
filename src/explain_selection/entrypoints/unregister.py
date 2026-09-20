"""SessionEnd hook: remove this session's registry entry."""

import logging
import sys
from collections.abc import Mapping

from explain_selection.entrypoints.hooks import build_hook_context, hook_main, log_result
from explain_selection.services import RegisterDeps, unregister_session

logger = logging.getLogger(__name__)


def run(stdin_text: str, environ: Mapping[str, str], deps: RegisterDeps) -> int:
    """Remove the entry for the session described by the hook input; always returns 0."""
    ctx = build_hook_context(stdin_text, environ)
    log_result(logger, "unregister", unregister_session(ctx, deps))
    return 0


def main() -> int:
    """Entry for ``python -m explain_selection.entrypoints.unregister``."""
    return hook_main(run)


__all__ = ["main", "run"]

if __name__ == "__main__":
    sys.exit(main())
