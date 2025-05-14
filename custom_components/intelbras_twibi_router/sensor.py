"""Sensors for Twibi mesh node statistics."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up sensors for Twibi mesh nodes."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]

    entities = []
    for node in coordinator.data["nodes"]:
        serial = node.get("sn")
        if node.get("role") != "1":
            device_id = (DOMAIN, serial)
            entities.append(
                NodeLinkQuality(
                    coordinator, node, serial,
                    key="link_quality",
                    name="Link Quality",
                    unit="dBm",
                    device_id=device_id
                )
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
            (n for n in self.coordinator.data["nodes"]
             if n.get("sn") == self._serial), {}
        )
        return current_node.get(self._key)

    @property
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
