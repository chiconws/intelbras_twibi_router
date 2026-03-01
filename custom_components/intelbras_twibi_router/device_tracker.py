"""Device tracker for Twibi Router integration."""

import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SELECTED_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up device tracker dynamically."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    # Initialize known MACs in coordinator
    if not hasattr(coordinator, "known_macs"):
        coordinator.known_macs = set()

    # Add listener for coordinator updates
    coordinator.async_add_listener(
        lambda: async_check_new_devices(hass, entry, async_add_entities)
    )
    # Initial entity creation
    async_check_new_devices(hass, entry, async_add_entities)


@callback
def async_check_new_devices(hass: HomeAssistant, entry, async_add_entities):
    """Check for new devices and create entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    host = entry_data["host"]

    online_devices = coordinator.data.get("online_list", [])
    current_macs = {dev["dev_mac"] for dev in online_devices}

    _LOGGER.debug("Found %d online devices: %s", len(online_devices), [f"{dev.get('dev_name', 'Unknown')} ({dev.get('dev_mac')})" for dev in online_devices])
    _LOGGER.debug("Current MACs: %s", current_macs)
    _LOGGER.debug("Known MACs: %s", coordinator.known_macs)

    # Find new MACs
    new_macs = current_macs - coordinator.known_macs
    _LOGGER.debug("New MACs to process: %s", new_macs)

    if not new_macs:
        _LOGGER.debug("No new devices to add")
        return

    # Get the list of selected devices
    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])

    # Create entities for new devices
    entities = []
    for mac in new_macs:
        # If selected_devices is configured and not empty, only add selected devices
        # If selected_devices is empty or not configured, add all devices
        if selected_devices and mac not in selected_devices:
            _LOGGER.debug("Skipping device %s - not in selected devices list", mac)
            continue

        device_info = next(
            (dev for dev in coordinator.data["online_list"] if dev["dev_mac"] == mac),
            {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
        )

        _LOGGER.debug("Creating device tracker for MAC: %s, Name: %s", mac, device_info.get("dev_name", "Unknown"))

        entities.append(
            TwibiDeviceTracker(coordinator, host, mac, device_info, entry.entry_id)
        )
        coordinator.known_macs.add(mac)

    if entities:
        async_add_entities(entities)


class TwibiDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a Twibi-connected device."""

    def __init__(
        self,
        coordinator,
        host,
        mac: str,
        device_info: dict,
        entry_id: str,
    ) -> None:
        """Initialize the device tracker."""

        super().__init__(coordinator)
        self._mac = mac
        self._host = host
        self._entry_id = entry_id
        self._device_info = device_info
        self._attr_entity_category = None
        self._attr_should_poll = False
        self._last_known_online_status = None  # Track last known status (None = unknown, True = online, False = offline)

        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, mac)},
            "manufacturer": "Unknown",
            "model": "Network Device",
            "name": device_info["dev_name"] or f"Device {mac}",
            "via_device": (DOMAIN, host),
        }

    async def async_added_to_hass(self):
        """Register device in the device registry on entity addition."""
        await super().async_added_to_hass()
        registry = dr.async_get(self.hass)
        registry.async_get_or_create(
            config_entry_id=self._entry_id, **self._attr_device_info
        )

    @property
    def device_info(self) -> dict:
        """Return device registry info for entity linking."""
        return self._attr_device_info

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self._device_info.get("dev_name")
            or f"Device {self.ip_address or self._mac}"
        )

    @property
    def online_list(self) -> list:
        """Return a list with the online devices."""
        return self.coordinator.data.get("online_list", [])

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        connected = self._mac in {dev.get("dev_mac") for dev in self.online_list}
        self._last_known_online_status = connected # Update last known online status
        return connected

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # The entity is always available if the coordinator is successfully updating
        if self.coordinator.last_update_success:
            return True

        # If coordinator failed to update, we need to decide based on last known status:
        # - If we never knew the status (None), assume device is offline and keep available
        # - If device was last known to be offline (False), keep it available so it shows as "Away"
        # - If device was last known to be online (True), make it unavailable since we lost connection
        if self._last_known_online_status is None or self._last_known_online_status is False:
            return True

        # Device was last known to be online but coordinator failed - mark as unavailable
        return False

    @property
    def state(self) -> str:
        """Return the state of the device."""
        # Explicitly return STATE_HOME or STATE_NOT_HOME based on connection status.
        # This ensures that a disconnected device is 'offline' (STATE_NOT_HOME)
        # even if the coordinator had a temporary hiccup, as long as the entity itself is 'available'.
        return STATE_HOME if self.is_connected else STATE_NOT_HOME

    @property
    def current_info(self) -> dict:
        """Return the current device information."""
        return next(
            (dev for dev in self.online_list if dev.get("dev_mac") == self._mac),
            self._device_info,
        )

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device, or None if unavailable."""
        return self.current_info.get("dev_ip")

    @property
    def connection_type(self) -> str:
        """Return the connection type of the device."""
        match self.current_info.get("wifi_mode"):
            case "--":
                return "Ethernet"
            case "AC":
                return "5GHz"
            case "BGN":
                return "2.4GHz"
            case _:
                return ""

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the device."""
        return {
            "mac": self._mac,
            "ip": self.ip_address,
            "connection": self.connection_type,
        }
