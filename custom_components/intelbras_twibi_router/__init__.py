"""Twibi Router integration."""

from datetime import timedelta
import logging
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TwibiCoordinator
from .runtime_data import TwibiRuntimeData
from .twibi_api import TwibiAPI
from .api.enums import NodeRole
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)

PLATFORMS = [
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

MODULES = ["node_info", "online_list", "wan_statistic"]

_LOGGER = logging.getLogger(__name__)


class _DeviceRegistryBaseKwargs(TypedDict, total=False):
    """Shared kwargs passed to device registry creation."""

    config_entry_id: str
    manufacturer: str
    model: str
    sw_version: str
    configuration_url: str


class _DeviceRegistryNodeKwargs(TypedDict, total=False):
    """Node-specific kwargs passed to device registry creation."""

    identifiers: set[tuple[str, str]]
    name: str
    via_device: tuple[str, str]


def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    entry_id: str,
    host: str,
    primary_device_identifier: str,
) -> None:
    """Migrate host-based entity unique IDs to the stable primary identifier."""
    if primary_device_identifier == host:
        return

    entity_registry = er.async_get(hass)
    old_prefix = f"{host}_"
    new_prefix = f"{primary_device_identifier}_"
    old_restart_unique_id = f"restart_{host}"
    new_restart_unique_id = f"restart_{primary_device_identifier}"

    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry_id):
        unique_id = entity_entry.unique_id
        if unique_id is None:
            continue

        if unique_id == old_restart_unique_id:
            new_unique_id = new_restart_unique_id
        elif unique_id.startswith(old_prefix):
            new_unique_id = unique_id.replace(old_prefix, new_prefix, 1)
        else:
            continue

        if new_unique_id == unique_id:
            continue

        try:
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=new_unique_id,
            )
        except ValueError:
            _LOGGER.warning(
                "Skipping unique_id migration for %s because %s already exists",
                entity_entry.entity_id,
                new_unique_id,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twibi integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_TWIBI_IP_ADDRESS]

    api = TwibiAPI(
        host,
        entry.data[CONF_PASSWORD],
        entry.data[CONF_EXCLUDE_WIRED],
        entry.data[CONF_UPDATE_INTERVAL],
        async_get_clientsession(hass),
    )

    coordinator = TwibiCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"{DOMAIN}_{host}",
        api=api,
        update_interval=timedelta(seconds=entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    nodes = sorted(
        coordinator.data.node_info,
        key=lambda node: 0 if node.role is NodeRole.PRIMARY else 1,
    )
    primary_node = next(
        (node for node in nodes if node.role is NodeRole.PRIMARY),
        None,
    )
    primary_device_identifier = primary_node.serial if primary_node else host
    _migrate_entity_unique_ids(
        hass,
        entry.entry_id,
        host,
        primary_device_identifier,
    )

    hass.data[DOMAIN][entry.entry_id] = TwibiRuntimeData(
        api=api,
        coordinator=coordinator,
        host=host,
        primary_device_identifier=primary_device_identifier,
    )

    for node in nodes:
        serial = node.serial
        serial_suffix = serial[-4:]
        model = node.device_name
        base_dr: _DeviceRegistryBaseKwargs = {
            "config_entry_id": entry.entry_id,
            "manufacturer": MANUFACTURER,
            "model": f"{model} {serial}",
            "sw_version": node.device_version,
        }
        node_ip = node.ip.strip()
        if node_ip:
            base_dr["configuration_url"] = f"http://{node_ip}"

        is_primary = node.role is NodeRole.PRIMARY
        node_dr: _DeviceRegistryNodeKwargs = {
            "identifiers": (
                {(DOMAIN, host), (DOMAIN, serial)}
                if is_primary
                else {(DOMAIN, serial)}
            ),
            "name": (
                f"{model} Primary {serial_suffix}"
                if is_primary
                else f"{model} Secondary {serial_suffix}"
            ),
        }
        if not is_primary:
            node_dr["via_device"] = (DOMAIN, primary_device_identifier)

        device_registry.async_get_or_create(
            **base_dr,
            **node_dr,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
