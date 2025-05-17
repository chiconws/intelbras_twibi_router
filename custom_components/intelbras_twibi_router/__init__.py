"""Twibi Router integration."""
from datetime import timedelta
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
from .coordinator import TwibiCoordinator

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

    async def async_update_data():
        """Fetch all data from the router."""
        try:
            await api.login()
            return await api.get_modules(["node_info", "online_list"])

        except APIError as err:
            _LOGGER.error("API update failed: %s", err)
            raise

        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise APIError(f"Unexpected error: {err}") from err

    coordinator = TwibiCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "host": host
    }

    device_registry = dr.async_get(hass)
    nodes = sorted(
        coordinator.data["node_info"],
        key=lambda n: 0 if n["role"] == "1" else 1
    )

    for node in nodes:
        serial = node["sn"]
        serial_suffix = serial[-4:]
        model = node["dut_name"]
        base_dr = {
            "config_entry_id": entry.entry_id,
            "manufacturer": MANUFACTURER,
            "model": f"{model} {serial}",
            "sw_version": node["dut_version"],
            "configuration_url": f"http://{node['ip']}",
        }
        if node["role"] == "1":
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
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
