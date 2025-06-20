"""Device tracker for Twibi Router integration."""

import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.components.sensor import SensorEntity
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
def async_check_new_devices(hass, entry, async_add_entities):
    """Check for new devices and create entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    host = entry_data["host"]
    api = entry_data["api"]

    current_macs = {dev["dev_mac"] for dev in coordinator.data.get("online_list", [])}

    # Find new MACs
    new_macs = current_macs - coordinator.known_macs
    if not new_macs:
        return

    # Get the list of selected devices
    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])
    
    # Create entities for new devices that are in the selected devices list
    entities = []
    for mac in new_macs:
        # Skip if the device is not in the selected devices list
        if selected_devices and mac not in selected_devices:
            continue
            
        device_info = next(
            (dev for dev in coordinator.data["online_list"] if dev["dev_mac"] == mac),
            {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
        )

        # Do not skip cabled devices if they are in the selected list
        # This ensures all selected devices get device tracker entities
        pass

        entities.append(
            TwibiDeviceTracker(coordinator, host, mac, device_info, entry.entry_id)
        )
        coordinator.known_macs.add(mac)

    if entities:
        async_add_entities(entities)
        
        # Create sensor entities for each device tracker, only for WiFi devices
        sensor_entities = []
        for tracker in entities:
            if tracker._device_info.get("wifi_mode") != "--":
                sensor_entities.extend([
                    TwibiTxRateSensor(coordinator, host, tracker._mac, tracker._device_info, entry.entry_id),
                    TwibiRssiSensor(coordinator, host, tracker._mac, tracker._device_info, entry.entry_id)
                ])
        if sensor_entities:
            async_add_entities(sensor_entities)


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
        return self._mac in {dev.get("dev_mac") for dev in self.online_list}

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
        match self.current_info.get("wifi_mode"):
            case "--":
                return "Ethernet"
            case "AC":
                return "5GHz"
            case "BGN":
                return "2.4GHz"
            case None:
                return ""
        return ""

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the device."""
        return {
            "mac": self._mac,
            "ip": self.ip_address,
            "connection": self.connection_type,
        }
        
def get_rssi_icon(rssi_value):
    """Return an icon based on RSSI signal strength."""
    try:
        rssi = int(rssi_value)
        if rssi >= -50:
            return "mdi:wifi-strength-4"
        elif rssi >= -60:
            return "mdi:wifi-strength-3"
        elif rssi >= -70:
            return "mdi:wifi-strength-2"
        elif rssi >= -80:
            return "mdi:wifi-strength-1"
        else:
            return "mdi:wifi-strength-outline"
    except (ValueError, TypeError):
        return "mdi:wifi-strength-outline"

class TwibiTxRateSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Twibi device's Tx Rate sensor."""

    def __init__(self, coordinator, host, mac: str, device_info: dict, entry_id: str) -> None:
        """Initialize the Tx Rate sensor."""
        super().__init__(coordinator)
        self._mac = mac
        self._host = host
        self._entry_id = entry_id
        self._device_info = device_info
        self._attr_entity_category = None
        self._attr_should_poll = False
        self._attr_icon = "mdi:transmission-tower"
        self._attr_native_unit_of_measurement = "Mbps"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, mac)},
            "manufacturer": "Unknown",
            "model": "Network Device",
            "name": device_info["dev_name"] or f"Device {mac}",
            "via_device": (DOMAIN, host),
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._mac}_tx_rate"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device_info.get('dev_name') or 'Device ' + self._mac} Tx Rate"

    @property
    def online_list(self) -> list:
        """Return a list with the online devices."""
        return self.coordinator.data.get("online_list", [])

    @property
    def current_info(self) -> dict:
        """Return the current device information."""
        return next(
            (dev for dev in self.online_list if dev.get("dev_mac") == self._mac),
            self._device_info,
        )

    @property
    def native_value(self) -> str:
        """Return the Tx Rate of the device."""
        return self.current_info.get("tx_rate", "0")

class TwibiRssiSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Twibi device's RSSI sensor."""

    def __init__(self, coordinator, host, mac: str, device_info: dict, entry_id: str) -> None:
        """Initialize the RSSI sensor."""
        super().__init__(coordinator)
        self._mac = mac
        self._host = host
        self._entry_id = entry_id
        self._device_info = device_info
        self._attr_entity_category = None
        self._attr_should_poll = False
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, mac)},
            "manufacturer": "Unknown",
            "model": "Network Device",
            "name": device_info["dev_name"] or f"Device {mac}",
            "via_device": (DOMAIN, host),
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._mac}_rssi"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._device_info.get('dev_name') or 'Device ' + self._mac} RSSI"

    @property
    def online_list(self) -> list:
        """Return a list with the online devices."""
        return self.coordinator.data.get("online_list", [])

    @property
    def current_info(self) -> dict:
        """Return the current device information."""
        return next(
            (dev for dev in self.online_list if dev.get("dev_mac") == self._mac),
            self._device_info,
        )

    @property
    def native_value(self) -> str:
        """Return the RSSI value of the device."""
        return self.current_info.get("rssi", "0")

    @property
    def icon(self) -> str:
        """Return the icon based on RSSI signal strength."""
        return get_rssi_icon(self.native_value)
