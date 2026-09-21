"""Typed exceptions for explain-selection."""


class ExplainSelectionError(Exception):
    """Base class for every error raised by this package."""


class InboxUnavailableError(ExplainSelectionError):
    """No inbox socket accepted the message for the chosen session."""


class RegistryError(ExplainSelectionError):
    """A registry file could not be written or read."""


class AgentsQueryError(ExplainSelectionError):
    """``claude agents --json`` failed or returned output that could not be parsed."""


class SubprocessError(ExplainSelectionError):
    """An injected subprocess runner failed to produce usable output."""


class InstallError(ExplainSelectionError):
    """An install step's file operation or macOS Services command failed."""


__all__ = [
    "AgentsQueryError",
    "ExplainSelectionError",
    "InboxUnavailableError",
    "InstallError",
    "RegistryError",
    "SubprocessError",
]
