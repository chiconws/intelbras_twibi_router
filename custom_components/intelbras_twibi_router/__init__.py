"""Twibi Router integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twibi Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    host = entry.data[CONF_TWIBI_IP_ADDRESS]
    password = entry.data[CONF_PASSWORD]
    exclude_wired = entry.data[CONF_EXCLUDE_WIRED]
    update_interval = entry.data[CONF_UPDATE_INTERVAL]
    session = async_get_clientsession(hass)

    # Register mesh nodes (secondary routers)
    api = TwibiAPI(host, password, exclude_wired, update_interval, session)
    try:
        nodes = await api.get_node_info()
    except Exception:
        nodes = []

    # Register primary router device
    device_registry = dr.async_get(hass)

    for node in nodes:
        node_ip = node.get("ip")
        serial = node.get("serial_number") or node.get("sn")
        model = node.get("dut_name")
        firmware = node.get("dut_version")

        if node.get("role") == "1":
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, host)},
                manufacturer=MANUFACTURER,
                name=f"Primary {model} ({host})",
                model=model,
                sw_version=firmware,
                configuration_url=f"http://{node_ip}",
            )

        else:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, serial)},
                manufacturer=MANUFACTURER,
                name=f"Secondary {model} {serial}",
                model=model,
                sw_version=firmware,
                configuration_url=f"http://{node_ip}",
                via_device=(DOMAIN, host),
            )

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["device_tracker", "sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["device_tracker", "sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
