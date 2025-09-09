"""Light for Twibi LED control."""
from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_v2 import TwibiAPI
from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up LED control switch for Twibi nodes."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    host = entry_data['host']
    api = entry_data['api']

    entities = []
    for node in coordinator.data["node_info"]:
        serial = node["sn"]
        if node["role"] == "1":
            device_id = (DOMAIN, host)
        else:
            device_id = (DOMAIN, serial)
        entities.append(
            TwibiLedLight(coordinator, api, serial, device_id)
        )

    async_add_entities(entities)

class TwibiLedLight(CoordinatorEntity, LightEntity):
    """Representation of a Twibi LED light."""

    def __init__(
        self,
        coordinator,
        api: TwibiAPI,
        serial: str,
        device_id: tuple,
    ) -> None:
        """Initialize the Twibi LED light."""

        super().__init__(coordinator)
        self._api = api
        self._serial = serial
        self._attr_unique_id = f"led_{serial}"
        self._attr_name = "Status LED"
        self._attr_icon = "mdi:led-on"
        self._attr_state_class = "on_off"
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._device_id = device_id
        self.entity_id = f"light.status_led_{serial[-4:]}"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {"identifiers": {self._device_id}}

    @property
    def is_on(self) -> bool:
        """Return None instead of False when unavailable."""
        node = next(
            (n for n in self.coordinator.data["node_info"]
             if n["sn"] == self._serial), {}
        )
        return node["led"] == "1"

    async def async_turn_on(self) -> None:
        """Turn on the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, True)

    async def async_turn_off(self) -> None:
        """Turn off the LED for the Twibi node."""
        await self.coordinator.async_set_led_status(self._serial, False)
