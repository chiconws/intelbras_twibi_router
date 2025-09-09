"""Button for Twibi Router integration."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api_v2 import TwibiAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up button for Twibi router."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    host = entry_data["host"]
    api = entry_data["api"]

    # Only add the restart button for the primary router
    primary_device_id = (DOMAIN, host)
    entities = [
        TwibiRestartButton(coordinator, api, host, primary_device_id)
    ]

    async_add_entities(entities)


class TwibiRestartButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Twibi restart button."""

    def __init__(
        self,
        coordinator,
        api: TwibiAPI,
        host: str,
        device_id: tuple,
    ) -> None:
        """Initialize the restart button."""
        super().__init__(coordinator)
        self._api = api
        self._host = host
        self._attr_unique_id = f"restart_{host}"
        self._attr_name = "Restart Router"
        self._attr_icon = "mdi:restart"
        self._attr_entity_category = EntityCategory.CONFIG
        self._device_id = device_id
        self.entity_id = f"button.restart_router_{host}"

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {"identifiers": {self._device_id}}

    async def async_press(self) -> None:
        """Handle the button press - restart the router."""
        _LOGGER.info("Restarting Twibi router %s", self._host)
        await self.coordinator.async_restart_router()
