"""Sensors for Twibi mesh node statistics."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    cached_property,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

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

    async_add_entities(entities)


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

    @cached_property
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

    @cached_property
    def icon(self) -> str | None:
        """Return the dynamic WiFi icon based on signal strength."""
        if (value := self.native_value) is None:
            return "mdi:wifi-strength-alert-outline"

        try:
            value = float(value)
        except (TypeError, ValueError):
            return "mdi:wifi-strength-alert-outline"

        if -50 <= value <= -30:
            return "mdi:wifi-strength-4"
        if -60 <= value < -50:
            return "mdi:wifi-strength-3"
        if -70 <= value < -60:
            return "mdi:wifi-strength-2"
        if -80 <= value < -70:
            return "mdi:wifi-strength-1"

        return "mdi:wifi-strength-alert-outline"


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

    @cached_property
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
