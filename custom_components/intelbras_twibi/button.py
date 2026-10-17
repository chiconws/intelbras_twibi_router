"""Button: reboot the mesh."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TwibiConfigEntry
from .entity import TwibiEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the reboot button."""
    coordinator = entry.runtime_data
    async_add_entities([TwibiRebootButton(coordinator, coordinator.data.primary.serial, "reboot")])


class TwibiRebootButton(TwibiEntity, ButtonEntity):
    """Reboot every node of the mesh."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Send the reboot command."""
        await self._async_command(self.coordinator.client.async_reboot(), refresh=False)
