"""FreeFeed MCP Server."""

from .client import FreeFeedAPIError, FreeFeedAuthError, FreeFeedClient
from .server import app, main

__version__ = "0.1.0"
__all__ = [
    "FreeFeedClient",
    "FreeFeedAPIError",
    "FreeFeedAuthError",
    "app",
    "main",
]
