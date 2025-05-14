"""Device tracker for Twibi Router integration."""
import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up device tracker dynamically."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    host = entry_data['host']

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    known_macs = set(stored_data.get(entry.entry_id, {}))

    online_macs = {
        device["dev_mac"] for device in coordinator.data["online"]
    }

    new_macs = online_macs - known_macs
    if new_macs:
        known_macs.update(new_macs)
        stored_data[entry.entry_id] = set(known_macs)
        await store.async_save(stored_data)

    entities = []
    added_macs = set()

    stored_data = await store.async_load() or {}
    known_macs = stored_data.get(entry.entry_id, [])

    for mac in known_macs:
        if mac not in added_macs:
            device_info = next(
                (dev for dev in coordinator.data["online"] if dev["dev_mac"] == mac),
                {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
            )
            entities.append(
                TwibiDeviceTracker(
                    coordinator,
                    host,
                    mac,
                    device_info,
                    entry.entry_id
                )
            )
            added_macs.add(mac)

    async_add_entities(entities)


class TwibiDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a Twibi-connected device."""

    def __init__(
        self,
        coordinator,
        host,
        mac: str,
        device_info: dict,
        entry_id: str,
    ) -> None:
        """Initialize the device tracker."""

        super().__init__(coordinator)
        self._mac = mac
        self._host = host
        self._entry_id = entry_id
        self._device_info = device_info
        self._attr_entity_category = None
        self._attr_should_poll = False

        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "connections": {(dr.CONNECTION_NETWORK_MAC, mac)},
            "manufacturer": "Unknown",
            "model": "Network Device",
            "name": device_info["dev_name"] or f"Device {mac}",
            "via_device": (DOMAIN, host),
        }

    async def async_added_to_hass(self):
        """Register device in the device registry on entity addition."""
        await super().async_added_to_hass()
        registry = dr.async_get(self.hass)
        registry.async_get_or_create(
            config_entry_id=self._entry_id,
            **self._attr_device_info
        )

    @property
    def device_info(self) -> dict:
        """Return device registry info for entity linking."""
        return self._attr_device_info

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the device."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return (
            self._device_info["dev_name"]
            or f"Device {self.ip_address or self._mac}"
        )

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        return self._mac in {dev["dev_mac"] for dev in self.coordinator.data["online"]}

    @property
    def current_info(self) -> dict:
        """Return the current device information."""
        return next(
            (dev for dev in self.coordinator.data["online"] if dev["dev_mac"] == self._mac),
            self._device_info,
        )

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device, or None if unavailable."""
        return self.current_info["dev_ip"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the device."""
        connection_type = self.current_info["wifi_mode"]
        return {
            "ip": self.ip_address,
            "mac": self._mac,
            "rssi": self.current_info["rssi"],
            "tx_rate": self.current_info["tx_rate"],
            "connection": "Ethernet" if connection_type == "--" else connection_type
        }
