"""Light for Twibi LED control."""
from datetime import timedelta
import logging

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import APIError, TwibiAPI
from .const import CONF_TWIBI_IP_ADDRESS, CONF_UPDATE_INTERVAL, DOMAIN
from .coordinator import TwibiCoordinator
from .utils import get_timestamp

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up LED control switch for Twibi nodes."""
    host = config_entry.data[CONF_TWIBI_IP_ADDRESS]
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    api = entry_data['api']

    async def async_update_nodes():
        try:
            return await api.get_node_info()

        except APIError as e:
            _LOGGER.warning("LED control error: %s", str(e))
            return []

    coordinator = TwibiCoordinator(
        hass,
        _LOGGER,
        name="twibi_node_led",
        update_method=async_update_nodes,
        update_interval=timedelta(seconds=config_entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = []
    for node in coordinator.data:
        serial = node.get("sn")
        if node.get("role") == "1":
            device_id = (DOMAIN, host)
        else:
            device_id = (DOMAIN, serial)
        entities.append(
            TwibiLedLight(coordinator, api, serial, device_id)
        )

    if entities:
        async_add_entities(entities)

class TwibiLedLight(CoordinatorEntity, LightEntity):
    """Representation of a Twibi LED light."""

    def __init__(
        self,
        coordinator,
        api: TwibiAPI,
        serial: str,
        device_id: tuple,
    ):
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
            (n for n in self.coordinator.data
             if n.get("sn") == self._serial), {}
        )
        return node.get("led") == "1"

    async def _async_set_led_status(self, status_led: str) -> None:
        payload = {
            "led": {
                "led_en": status_led,
                "sn": self._serial,
                "timestamp": str(get_timestamp()),
            }
        }
        await self._api.session.post(self._api.set_url, json=payload)

        await self.coordinator.async_refresh()

    async def async_turn_on(self) -> None:
        """Turn on the LED for the Twibi node."""
        await self._async_set_led_status("1")

    async def async_turn_off(self) -> None:
        """Turn off the LED for the Twibi node."""
        await self._async_set_led_status("0")
