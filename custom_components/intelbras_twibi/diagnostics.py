"""Diagnostics: the raw router reply with secrets removed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import TwibiConfigEntry

TO_REDACT = {CONF_PASSWORD, "guest_pass", "pass", "sn", "serial_number", "groupsn", "ip", "dev_ip"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TwibiConfigEntry
) -> dict[str, Any]:
    """Return what the router reported on the last poll."""
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "router": async_redact_data(entry.runtime_data.data.raw, TO_REDACT),
    }
