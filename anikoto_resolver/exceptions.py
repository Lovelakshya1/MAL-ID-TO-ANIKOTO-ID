"""
Anikoto Resolver Exception Classes
"""

class AnikotoError(Exception):
    """Base exception for all anikoto-resolver errors."""
    pass


class ResolveError(AnikotoError):
    """Raised when an anime cannot be confidently resolved."""
    pass


class JikanAPIError(AnikotoError):
    """Raised when Jikan API request fails after maximum retries."""
    pass


class AnikotoAPIError(AnikotoError):
    """Raised when Anikoto search or watch endpoint fails."""
    pass
