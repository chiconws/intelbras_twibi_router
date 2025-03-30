"""Twibi Router integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twibi Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Store config entry data
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Twibi Tracker entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "device_tracker")

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
