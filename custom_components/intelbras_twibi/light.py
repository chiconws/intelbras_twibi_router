"""Light: the status LED of each node."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TwibiConfigEntry
from .entity import TwibiEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create one LED light per node."""
    coordinator = entry.runtime_data
    async_add_entities(TwibiLed(coordinator, n.serial, "led") for n in coordinator.data.nodes)


class TwibiLed(TwibiEntity, LightEntity):
    """Status LED on the front of a node."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self) -> bool | None:
        """Return the LED state."""
        node = self.node
        return node.led_on if node else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the LED on."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the LED off."""
        await self._set(False)

    async def _set(self, on: bool) -> None:
        await self._async_command(self.coordinator.client.async_set_led(self._serial, on))
