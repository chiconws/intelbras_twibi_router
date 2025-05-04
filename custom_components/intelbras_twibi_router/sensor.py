"""Sensors for Twibi mesh node statistics."""
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

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up sensors for Twibi mesh nodes."""
    host = entry.data[CONF_TWIBI_IP_ADDRESS]
    session = async_get_clientsession(hass)

    api = TwibiAPI(
        host,
        entry.data[CONF_PASSWORD],
        entry.data[CONF_EXCLUDE_WIRED],
        entry.data[CONF_UPDATE_INTERVAL],
        session
    )

    async def async_update_nodes():
        try:
            return await api.get_node_info()
        except Exception:
            _LOGGER.exception("Failed fetching node info")
            return []

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_node_info",
        update_method=async_update_nodes,
        update_interval=timedelta(seconds=entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = []
    for node in coordinator.data:
        if node.get("role") != "1":
            serial = node.get("serial_number") or node.get("sn")
            device_id = (DOMAIN, serial)
            # Link quality sensor
            entities.append(NodeMetricSensor(coordinator, node, serial, "link_quality", "Link Quality", "dBm", device_id))

    async_add_entities(entities)

class NodeMetricSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a specific node metric."""

    def __init__(self, coordinator, node, serial, key, name, unit, device_id):
        super().__init__(coordinator)
        self._serial = serial
        self._key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_class = None
        self._device_id = device_id

    @property
    def device_info(self):
        """Return the device registry info."""
        return {"identifiers": {self._device_id}}

    @property
    def native_value(self):
        """Return the current value of this sensor."""
        nodes = self.coordinator.data
        node = next((n for n in nodes if (n.get("serial_number") or n.get("sn")) == self._serial), {})
        val = node.get(self._key)
        # Convert numeric fields
        try:
            if self._key in ("link_quality", "Uptime"):
                return int(val)
        except Exception:
            pass
        return val
