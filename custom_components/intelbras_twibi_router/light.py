"""Light for Twibi LED control."""

from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.enums import NodeLedState
from .coordinator import TwibiCoordinator
from .helpers import build_router_device_info, get_node_device_identifier
from .runtime_data import get_runtime_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LED control switch for Twibi nodes."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator: TwibiCoordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    entities = []
    for node in coordinator.data.node_info:
        entities.append(
            TwibiLedLight(
                coordinator,
                get_node_device_identifier(node, primary_device_identifier),
                node.serial,
            )
        )

    async_add_entities(entities)


class TwibiLedLight(LightEntity):
    """Representation of a Twibi LED light."""

    coordinator: TwibiCoordinator

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        serial: str,
    ) -> None:
        """Initialize the Twibi LED light."""
        super().__init__()
        self.coordinator = coordinator
        self._device_identifier = device_identifier
        self._serial = serial
        self._attr_should_poll = False
        self._attr_unique_id = f"led_{serial}"
        self._attr_name = "Status LED"
        self._attr_icon = "mdi:led-on"
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_device_info = build_router_device_info(device_identifier)
        self._update_state()

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh light state from coordinator data."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        """Update cached state from the coordinator."""
        node = self.coordinator.get_node_by_serial(self._serial)
        self._attr_is_on = node is not None and node.led is NodeLedState.ON
        self._attr_available = self.coordinator.last_update_success and node is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, False)
