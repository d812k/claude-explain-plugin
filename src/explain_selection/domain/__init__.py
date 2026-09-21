"""Pure logic: no I/O, no clocks, no environment."""

from explain_selection.domain.deeplink import (
    DEEP_LINK_QUERY_LIMIT,
    DEEP_LINK_TRUNCATION_MARKER,
    build_deep_link,
    fit_prompt_for_deep_link,
)
from explain_selection.domain.models import (
    REGISTRY_FORMAT_VERSION,
    InboxToken,
    LiveSession,
    Pid,
    RegistryEntry,
    SessionId,
    SessionKind,
    SessionStatus,
)
from explain_selection.domain.selection import (
    TEXT_PLACEHOLDER,
    TRUNCATION_MARKER,
    Selection,
    clean_selection,
    render_prompt,
)
from explain_selection.domain.socket_path import (
    MAX_SOCKET_PATH_BYTES,
    candidate_socket_paths,
    pid_from_socket_path,
)
from explain_selection.domain.targeting import (
    Choose,
    Decision,
    Focus,
    Inject,
    OpenNewWindow,
    PickReason,
    RememberedTarget,
    Target,
    chooser_order,
    describe_target,
    join_targets,
    select_target,
)
from explain_selection.domain.wire import encode_inbox_lines

__all__ = [
    "DEEP_LINK_QUERY_LIMIT",
    "DEEP_LINK_TRUNCATION_MARKER",
    "MAX_SOCKET_PATH_BYTES",
    "REGISTRY_FORMAT_VERSION",
    "TEXT_PLACEHOLDER",
    "TRUNCATION_MARKER",
    "Choose",
    "Decision",
    "Focus",
    "InboxToken",
    "Inject",
    "LiveSession",
    "OpenNewWindow",
    "PickReason",
    "Pid",
    "RegistryEntry",
    "RememberedTarget",
    "Selection",
    "SessionId",
    "SessionKind",
    "SessionStatus",
    "Target",
    "build_deep_link",
    "candidate_socket_paths",
    "chooser_order",
    "clean_selection",
    "describe_target",
    "encode_inbox_lines",
    "fit_prompt_for_deep_link",
    "join_targets",
    "pid_from_socket_path",
    "render_prompt",
    "select_target",
]
