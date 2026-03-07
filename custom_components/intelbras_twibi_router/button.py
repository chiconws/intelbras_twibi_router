"""Button for Twibi Router integration."""
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .coordinator import TwibiCoordinator
from .const import DOMAIN
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up button for Twibi router."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator = runtime_data.coordinator
    host = runtime_data.host
    primary_device_identifier = runtime_data.primary_device_identifier

    # Only add the restart button for the primary router
    primary_device_id = (DOMAIN, primary_device_identifier)
    entities = [
        TwibiRestartButton(
            coordinator,
            host,
            primary_device_identifier,
            primary_device_id,
        )
    ]

    async_add_entities(entities)


class TwibiRestartButton(ButtonEntity):
    """Representation of a Twibi restart button."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        host: str,
        primary_device_identifier: str,
        device_id: tuple[str, str],
    ) -> None:
        """Initialize the restart button."""
        self.coordinator = coordinator
        self._host = host
        self._attr_unique_id = f"restart_{primary_device_identifier}"
        self._attr_name = "Restart Router"
        self._attr_icon = "mdi:restart"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_device_info = {"identifiers": {device_id}}
        self._attr_suggested_object_id = f"restart_router_{slugify(primary_device_identifier)}"
        self._attr_available = coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update availability from the coordinator."""
        self._attr_available = self.coordinator.last_update_success
        self.async_write_ha_state()

    async def async_press(self) -> None:
        """Handle the button press - restart the router."""
        _LOGGER.info("Restarting Twibi router %s", self._host)
        await self.coordinator.async_restart_router()
