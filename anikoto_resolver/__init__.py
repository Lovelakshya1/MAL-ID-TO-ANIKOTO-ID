"""
Anikoto Resolver - Production-grade Anime MAL ID & Title Resolver for Anikoto.cz
"""

from .core import AnikotoResolver, resolve, resolve_from_titles
from .exceptions import AnikotoError, ResolveError, JikanAPIError, AnikotoAPIError

__version__ = "1.0.0"
__author__ = "Himmy Team"

__all__ = [
    "AnikotoResolver",
    "resolve",
    "resolve_from_titles",
    "AnikotoError",
    "ResolveError",
    "JikanAPIError",
    "AnikotoAPIError",
]
