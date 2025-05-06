"""Utility functions for Intelbras Twibi Router integration."""

from datetime import datetime


def get_timestamp() -> str:
    """Get current timestamp in milliseconds."""
    return int(datetime.now().timestamp() * 1000)

def normalize_mac(mac: str) -> str:
    """Normalize MAC address to colon-separated lowercase."""
    mac = mac.lower().replace("-", "").replace(":", "").strip()
    return ":".join(mac[i:i+2] for i in range(0, 12, 2))
