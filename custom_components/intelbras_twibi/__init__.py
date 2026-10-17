"""The Intelbras Twibi integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwibiClient
from .coordinator import TwibiConfigEntry, TwibiCoordinator
from .entity import node_device_info

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: TwibiConfigEntry) -> bool:
    """Connect to the router and set up the platforms."""
    client = TwibiClient(entry.data[CONF_HOST], entry.data[CONF_PASSWORD], async_get_clientsession(hass))
    coordinator = TwibiCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    # Register the primary unit first so the other units can point at it.
    primary = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **node_device_info(coordinator.data.primary)
    )
    coordinator.primary_device_id = primary.id
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TwibiConfigEntry) -> bool:
    """Unload the platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: TwibiConfigEntry) -> None:
    """Apply changed options."""
    await hass.config_entries.async_reload(entry.entry_id)
