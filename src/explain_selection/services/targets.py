"""The step every use case shares: list live sessions, drop dead registry entries, pair by pid.

Package-private: ``deliver``, ``send`` and ``sessions`` import from here; nothing outside the
services package does.
"""

from explain_selection.domain import Target, join_targets
from explain_selection.services.protocols import (
    InboxAddress,
    ProcessProbe,
    RegistryStore,
    SessionLister,
)


def live_targets(
    sessions: SessionLister, registry: RegistryStore, probe: ProcessProbe
) -> tuple[Target, ...]:
    """Interactive sessions paired with their registry entries, sorted by pid.

    An entry whose pid ``claude agents`` does not list may still belong to a session the CLI
    failed to report; only a pid the kernel no longer knows is pruned from the registry.
    """
    live = sessions.list_interactive()
    entries = registry.read_all()
    live_pids = {s.pid for s in live}
    for entry in entries:
        if entry.pid not in live_pids and not probe.is_alive(entry.pid):
            registry.delete(entry.pid)
    return join_targets(live, entries)


def address_for(target: Target) -> InboxAddress:
    """The registered socket and token when there is an entry; pid-derived paths otherwise."""
    entry = target.entry
    return InboxAddress(
        pid=target.session.pid,
        socket_path=entry.socket if entry is not None else None,
        token=entry.token if entry is not None else None,
    )


__all__ = ["address_for", "live_targets"]
