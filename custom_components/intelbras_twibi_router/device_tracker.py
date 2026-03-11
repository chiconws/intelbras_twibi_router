"""Device tracker for Twibi Router integration."""

import logging
from typing import Any, cast

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.models import OnlineDevice
from .coordinator import TwibiCoordinator
from .const import CONF_SELECTED_DEVICES, CONF_TRACK_ALL_DEVICES, DOMAIN
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker dynamically."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator: TwibiCoordinator = runtime_data.coordinator

    # Add listener for coordinator updates
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: async_check_new_devices(hass, entry, async_add_entities)
        )
    )
    # Initial entity creation
    async_check_new_devices(hass, entry, async_add_entities)


@callback
def async_check_new_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Check for new devices and create entities."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator: TwibiCoordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    online_devices = coordinator.data.online_list
    online_by_mac = {device.mac: device for device in online_devices}
    current_macs = set(online_by_mac)
    registered_macs = _get_registered_tracker_macs(hass, entry.entry_id)
    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])
    track_all_devices = entry.data.get(
        CONF_TRACK_ALL_DEVICES,
        not selected_devices,
    )

    if track_all_devices:
        desired_macs = current_macs | registered_macs
    else:
        desired_macs = set(selected_devices or [])

    _LOGGER.debug(
        "Found %d online devices: %s",
        len(online_devices),
        [f"{device.display_name} ({device.mac})" for device in online_devices],
    )
    _LOGGER.debug("Current MACs: %s", current_macs)
    _LOGGER.debug("Registered MACs: %s", registered_macs)
    _LOGGER.debug("Known MACs: %s", coordinator.known_macs)

    # Find new MACs that should exist as entities, even when currently offline.
    new_macs = desired_macs - coordinator.known_macs
    _LOGGER.debug("New MACs to process: %s", new_macs)

    if not new_macs:
        _LOGGER.debug("No new devices to add")
        return

    # Create entities for new devices
    entities = []
    stored_names = _get_registered_tracker_names(hass, entry.entry_id)
    for mac in sorted(new_macs):
        device_info = online_by_mac.get(mac)
        device_name = (
            device_info.display_name
            if device_info is not None
            else stored_names.get(mac) or f"Device {mac}"
        )

        _LOGGER.debug("Creating device tracker for MAC: %s, Name: %s", mac, device_name)

        entities.append(
            TwibiDeviceTracker(
                coordinator,
                primary_device_identifier,
                mac,
                device_name,
                entry.entry_id,
            )
        )
        coordinator.known_macs.add(mac)

    if entities:
        async_add_entities(entities)


@callback
def _get_registered_tracker_macs(hass: HomeAssistant, entry_id: str) -> set[str]:
    """Return MACs for tracker entities already stored in the entity registry."""
    registry = er.async_get(hass)
    return {
        entity_entry.unique_id
        for entity_entry in er.async_entries_for_config_entry(registry, entry_id)
        if entity_entry.platform == DOMAIN
        and entity_entry.domain == "device_tracker"
        and entity_entry.unique_id
    }


@callback
def _get_registered_tracker_names(hass: HomeAssistant, entry_id: str) -> dict[str, str]:
    """Return stored names for known network devices keyed by MAC."""
    registry = dr.async_get(hass)
    stored_names: dict[str, str] = {}

    for device_entry in dr.async_entries_for_config_entry(registry, entry_id):
        mac = next(
            (
                value
                for connection_type, value in device_entry.connections
                if connection_type == dr.CONNECTION_NETWORK_MAC
            ),
            None,
        )
        if mac:
            stored_names[mac] = device_entry.name_by_user or device_entry.name or ""

    return stored_names


class TwibiDeviceTracker(ScannerEntity):
    """Representation of a Twibi-connected device."""

    coordinator: TwibiCoordinator

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        primary_device_identifier: str,
        mac: str,
        device_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__()
        self.coordinator = coordinator
        self._mac = mac
        self._primary_device_identifier = primary_device_identifier
        self._entry_id = entry_id
        self._device_name = device_name
        self._last_known_online_status: bool | None = None
        self._attr_should_poll = False
        self._attr_name = device_name
        self._attr_mac_address = mac
        self._update_cached_attributes()

    async def async_internal_added_to_hass(self) -> None:
        """Create the client device before ScannerEntity attaches to it."""
        dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self._entry_id,
            identifiers={(DOMAIN, self._mac)},
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac)},
            manufacturer="Unknown",
            model="Network Device",
            name=self._device_name,
            via_device=(DOMAIN, self._primary_device_identifier),
        )
        await super().async_internal_added_to_hass()

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def online_list(self) -> list[OnlineDevice]:
        """Return a list with the online devices."""
        return self.coordinator.data.online_list

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update cached attributes and availability from coordinator data."""
        self._update_cached_attributes()
        self.async_write_ha_state()

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        connected = self.current_info is not None
        self._last_known_online_status = connected
        return connected

    def _update_cached_attributes(self) -> None:
        """Refresh cached entity attributes from coordinator state."""
        current_info = self.current_info
        self._attr_ip_address = current_info.ip if current_info else None
        self._attr_hostname = (
            current_info.display_name if current_info else self._device_name
        )
        self._attr_name = current_info.display_name if current_info else self._device_name
        self._attr_extra_state_attributes = {
            "mac": self._mac,
            "ip": self._attr_ip_address,
            "connection": self.connection_type,
        }

        # The entity is always available if the coordinator is successfully updating
        if self.coordinator.last_update_success:
            self._attr_available = True
        else:
            # If coordinator failed to update, keep entities that were already offline
            # available so they remain "away". Only previously online devices become
            # unavailable when we lose contact with the router.
            self._attr_available = not self._last_known_online_status

        cache = cast(dict[str, Any], self.__dict__)
        for cache_key in (
            "available",
            "name",
            "ip_address",
            "hostname",
            "extra_state_attributes",
        ):
            cache.pop(cache_key, None)

    @property
    def current_info(self) -> OnlineDevice | None:
        """Return the current device information."""
        return self.coordinator.data.get_device_by_mac(self._mac)

    @property
    def connection_type(self) -> str:
        """Return the connection type of the device."""
        current_info = self.current_info
        return current_info.connection_type if current_info else ""
