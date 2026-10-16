"""Errors raised by external provider wrappers."""


class ProviderError(Exception):
    """Raised when an external provider is unreachable or returns unusable data."""