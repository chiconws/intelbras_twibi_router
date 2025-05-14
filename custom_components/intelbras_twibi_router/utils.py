"""Utility functions for Intelbras Twibi Router integration."""

from datetime import datetime


def get_timestamp() -> str:
    """Get current timestamp in milliseconds."""
    return int(datetime.now().timestamp() * 1000)
