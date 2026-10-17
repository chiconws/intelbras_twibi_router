"""Binary sensor: is the primary node online."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TwibiConfigEntry
from .entity import TwibiEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the WAN connectivity sensor."""
    coordinator = entry.runtime_data
    async_add_entities([TwibiWanSensor(coordinator, coordinator.data.primary.serial, "wan")])


class TwibiWanSensor(TwibiEntity, BinarySensorEntity):
    """Internet connection of the primary node."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool | None:
        """Return whether the WAN link is up."""
        node = self.node
        return node.wan_connected if node else None
