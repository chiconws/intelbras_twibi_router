"""Twibi Router integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APIError, TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.LIGHT,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twibi integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_TWIBI_IP_ADDRESS]

    api = TwibiAPI(
        host,
        entry.data[CONF_PASSWORD],
        entry.data[CONF_EXCLUDE_WIRED],
        entry.data[CONF_UPDATE_INTERVAL],
        async_get_clientsession(hass)
    )

    try:
        await api.login()
        nodes = await api.get_node_info()
    except APIError as e:
        _LOGGER.error("Failed to login or fetch nodes: %s", e)
        nodes = []

    hass.data[DOMAIN][entry.entry_id] = {'api': api, 'data': entry.data}

    device_registry = dr.async_get(hass)
    for node in nodes:
        serial = node.get("sn")
        serial_suffix = serial[-4:]
        model = node.get("dut_name")
        base_dr = {
            "config_entry_id": entry.entry_id,
            "manufacturer": MANUFACTURER,
            "model": f"{model} {serial}",
            "sw_version": node.get("dut_version"),
            "configuration_url": f"http://{node.get('ip')}",
        }
        if node.get("role") == "1":
            primary = " " if len(nodes) == 1 else " Primary "
            device_registry.async_get_or_create(
                **base_dr,
                identifiers={(DOMAIN, host)},
                name=f"{model}{primary}{serial_suffix}"
            )
        else:
            device_registry.async_get_or_create(
                **base_dr,
                identifiers={(DOMAIN, serial)},
                name=f"{model} Secondary {serial_suffix}",
                via_device=(DOMAIN, host)
            )

    await hass.config_entries.async_forward_entry_setups(
        entry, PLATFORMS
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
