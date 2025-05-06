"""Light for Twibi LED control."""
from datetime import timedelta
import logging

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from .utils import get_timestamp

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up LED control switch for Twibi nodes."""
    host = entry.data[CONF_TWIBI_IP_ADDRESS]
    password = entry.data[CONF_PASSWORD]
    exclude_wired = entry.data[CONF_EXCLUDE_WIRED]
    update_interval = entry.data[CONF_UPDATE_INTERVAL]
    session = async_get_clientsession(hass)

    api = TwibiAPI(
        host,
        password,
        exclude_wired,
        update_interval,
        session
    )

    async def async_update_nodes():
        try:
            return await api.get_node_info()
        except Exception:
            _LOGGER.exception("Failed fetching node info for LED")
            return []

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_node_led",
        update_method=async_update_nodes,
        update_interval=timedelta(seconds=update_interval),
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
    async_add_entities(entities)

class TwibiLedLight(CoordinatorEntity, LightEntity):
    """Toggle node LED."""

    def __init__(
        self,
        coordinator,
        api: TwibiAPI,
        serial: str,
        device_id: tuple,
    ):
        """Initialize the Twibi LED light.

        Args:
            coordinator: The data update coordinator for managing updates.
            api (TwibiAPI): The API instance for interacting with the Twibi device.
            serial (str): The serial number of the Twibi node.
            device_id (tuple): The unique identifier for the device.

        """
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
        """Return device information for the Twibi node."""
        return {"identifiers": {self._device_id}}

    @property
    def is_on(self) -> bool:
        """Return True if the LED is on, False otherwise."""
        node = next(
            (n for n in self.coordinator.data
             if (n.get("sn")) == self._serial), {}
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
