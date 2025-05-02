"""Sensors for Twibi Router integration."""

from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up sensors."""
    host = config_entry.data[CONF_TWIBI_IP_ADDRESS]
    session = async_get_clientsession(hass)

    twibi = TwibiAPI(
        host,
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_EXCLUDE_WIRED],
        config_entry.data[CONF_UPDATE_INTERVAL],
        session
    )

    async def async_update_data():
        """Fetch WAN statistics."""
        return await twibi.get_wan_statistics()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_wan_stats",
        update_method=async_update_data,
        update_interval=timedelta(seconds=config_entry.data[CONF_UPDATE_INTERVAL]),
    )

    entities = [
        TwibiUsageSensor(coordinator, host, "download", "Total Download", "mdi:download"),
        TwibiUsageSensor(coordinator, host, "upload", "Total Upload", "mdi:upload"),
    ]

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(entities)


class TwibiUsageSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Twibi usage sensor."""

    def __init__(self, coordinator, host, usage_type, name, icon) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._usage_type = usage_type
        self._attr_name = f"Twibi {name}"
        self._attr_icon = icon
        self._attr_unique_id = f"twibi_{usage_type}_usage"
        self._attr_native_unit_of_measurement = "MB"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"Twibi Router ({host})",
            "manufacturer": "Intelbras",
            "model": "Twibi Router",
            "configuration_url": f"http://{host}",
        }

    @property
    def native_value(self):
        """Return the sensor value."""
        key = f"ttotal_{'down' if self._usage_type == 'download' else 'up'}"
        value = self.coordinator.data.get(key)
        _LOGGER.debug("Sensor %s value: %s", self._attr_name, value)
        try:
            return round(int(value), 2)
        except ValueError:
            return 0

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.last_update_success
