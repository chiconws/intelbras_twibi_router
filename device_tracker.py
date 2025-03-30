"""Device tracker for Twibi Router integration."""

from datetime import timedelta
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.core import HomeAssistant, callback
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
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up device tracker dynamically."""
    session = async_get_clientsession(hass)
    twibi = TwibiAPI(
        config_entry.data[CONF_TWIBI_IP_ADDRESS],
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_EXCLUDE_WIRED],
        config_entry.data[CONF_UPDATE_INTERVAL],
        session,
    )

    async def async_update_data():
        data = await twibi.get_online_list()
        return data if isinstance(data, list) else []

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=twibi.update_interval),
    )

    await coordinator.async_refresh()

    known_macs = set()

    @callback
    def async_check_for_new_devices():
        new_entities = []
        for dev in coordinator.data:
            if dev["dev_mac"] not in known_macs:
                known_macs.add(dev["dev_mac"])
                new_entities.append(
                    TwibiDeviceTracker(coordinator, dev["dev_mac"], dev)
                )
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(async_check_for_new_devices)
    )
    async_check_for_new_devices()


class TwibiDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a Twibi-connected device."""

    def __init__(self, coordinator, mac, device_info) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._mac = mac
        self._device_info = device_info

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self._device_info.get("dev_name")
            or f"Device {self._device_info.get('dev_ip')}"
        )

    @property
    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        return any(dev["dev_mac"] == self._mac for dev in self.coordinator.data)

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device_info.get("dev_ip")

    @property
    def extra_state_attributes(self):
        """Return additional state attributes for the device."""
        return {
            "ip": self._device_info.get("dev_ip"),
            "mac": self._mac,
            "rssi": self._device_info.get("rssi"),
            "tx_rate": self._device_info.get("tx_rate"),
            "wifi_mode": self._device_info.get("wifi_mode"),
        }
