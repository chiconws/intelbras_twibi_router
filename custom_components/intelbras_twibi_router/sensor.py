"""Sensors for Twibi mesh node statistics and device-specific metrics."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SELECTED_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up sensors for Twibi mesh nodes."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data.get("coordinator")
    host = entry_data.get("host")

    entities = []
    for node in coordinator.data.get("node_info"):
        serial = node.get("sn")
        if node.get("role") != "1":
            entities.append(
                NodeLinkQuality(
                    coordinator,
                    node,
                    serial,
                    key="link_quality",
                    name="Link Quality",
                    unit="dBm",
                    device_id=(DOMAIN, serial),
                )
            )

    primary_device_id = (DOMAIN, host)
    entities.extend(
        [
            UploadSpeedSensor(coordinator, host, primary_device_id),
            DownloadSpeedSensor(coordinator, host, primary_device_id),
        ]
    )

    if not hasattr(coordinator, "known_macs"):
        coordinator.known_macs = set()

    selected_devices = entry.data.get(CONF_SELECTED_DEVICES, [])

    device_sensors = []
    for device in coordinator.data.get("online_list", []):
        mac = device.get("dev_mac")
        if mac and device.get("wifi_mode") != "--" and (not selected_devices or mac in selected_devices):
            device_sensors.extend([
                TwibiTxRateSensor(coordinator, host, mac, device, entry.entry_id),
                TwibiRssiSensor(coordinator, host, mac, device, entry.entry_id)
            ])
            coordinator.known_macs.add(mac)

    if device_sensors:
        entities.extend(device_sensors)

    async_add_entities(entities)

def get_rssi_icon(rssi_value):
    """Return an icon based on RSSI signal strength."""
    try:
        rssi = int(rssi_value)
    except (ValueError, TypeError):
        return "mdi:wifi-strength-outline"

    thresholds = [
        (-50, "mdi:wifi-strength-4"),
        (-60, "mdi:wifi-strength-3"),
        (-70, "mdi:wifi-strength-2"),
        (-80, "mdi:wifi-strength-1"),
    ]

    for limit, icon in thresholds:
        if rssi >= limit:
            return icon

    return "mdi:wifi-strength-outline"


class NodeLinkQuality(CoordinatorEntity, SensorEntity):
    """Representation of a node link quality sensor."""

    def __init__(self, coordinator, node, serial, key, name, unit, device_id):
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._node = node
        self._serial = serial
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{serial}_{key}"
        self._device_id = device_id
        self.entity_id = f"sensor.link_quality_{serial[-4:]}"
        self._attr_entity_registry_enabled_default = False

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {"identifiers": {self._device_id}}

    @property
    def native_value(self):
        """Return None when API is unavailable to clear the state."""
        if not self.coordinator.last_update_success:
            return None

        current_node = next(
            (
                n
                for n in self.coordinator.data["node_info"]
                if n.get("sn") == self._serial
            ),
            {},
        )
        return current_node[self._key]

    @property
    def icon(self) -> str | None:
        """Return the dynamic WiFi icon based on signal strength."""
        return get_rssi_icon(self.native_value)


class SpeedSensor(CoordinatorEntity, SensorEntity):
    """Base class for speed sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "kbit/s"
    _attr_suggested_unit_of_measurement = "Mbit/s"
    _attr_device_class = SensorDeviceClass.DATA_RATE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, host, device_id, key, name_suffix):
        """Initialize speed sensors."""
        super().__init__(coordinator)
        self._host = host
        self._key = key
        self._attr_name = f"{name_suffix} Speed"
        self._attr_unique_id = f"{host}_{key}_speed"
        self._attr_device_info = {"identifiers": {device_id}}
        self.entity_id = f"sensor.{host}_{key}_speed"

    @property
    def native_value(self):
        """Return the speed value in kbps."""
        try:
            return float(self.coordinator.data["wan_statistic"][0][self._key])
        except (KeyError, ValueError, IndexError, TypeError):
            return None


class UploadSpeedSensor(SpeedSensor):
    """Upload speed sensor."""

    def __init__(self, coordinator, host, device_id):
        """Initialize upload speed sensor."""
        super().__init__(
            coordinator=coordinator,
            host=host,
            device_id=device_id,
            key="up_speed",
            name_suffix="Upload",
        )


class DownloadSpeedSensor(SpeedSensor):
    """Download speed sensor."""

    def __init__(self, coordinator, host, device_id):
        """Initialize download speed sensor."""
        super().__init__(
            coordinator=coordinator,
            host=host,
            device_id=device_id,
            key="down_speed",
            name_suffix="Download",
        )

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
