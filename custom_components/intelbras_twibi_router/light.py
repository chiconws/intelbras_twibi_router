"""Light for Twibi LED control."""
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.enums import NodeLedState, NodeRole
from .const import DOMAIN
from .runtime_data import get_runtime_data


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up LED control switch for Twibi nodes."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    entities = []
    for node in coordinator.data.node_info:
        serial = node.serial
        if node.role is NodeRole.PRIMARY:
            device_id = (DOMAIN, primary_device_identifier)
        else:
            device_id = (DOMAIN, serial)
        entities.append(
            TwibiLedLight(coordinator, serial, device_id)
        )

    async_add_entities(entities)

class TwibiLedLight(CoordinatorEntity, LightEntity):
    """Representation of a Twibi LED light."""

    def __init__(
        self,
        coordinator,
        serial: str,
        device_id: tuple,
    ) -> None:
        """Initialize the Twibi LED light."""

        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = f"led_{serial}"
        self._attr_name = "Status LED"
        self._attr_icon = "mdi:led-on"
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._device_id = device_id

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {"identifiers": {self._device_id}}

    @property
    def is_on(self) -> bool:
        """Return None instead of False when unavailable."""
        node = self.coordinator.get_node_by_serial(self._serial)
        return node is not None and node.led is NodeLedState.ON

    async def async_turn_on(self) -> None:
        """Turn on the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, True)

    async def async_turn_off(self) -> None:
        """Turn off the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, False)
