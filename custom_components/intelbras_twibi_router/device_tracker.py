"""Device tracker for Twibi Router integration."""

from datetime import timedelta
import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import APIError
from .const import CONF_TWIBI_IP_ADDRESS, CONF_UPDATE_INTERVAL, DOMAIN
from .coordinator import TwibiCoordinator
from .utils import normalize_mac

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up device tracker dynamically."""
    host = config_entry.data[CONF_TWIBI_IP_ADDRESS]
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    api = entry_data['api']

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    known_macs = {
        normalize_mac(mac)
        for mac in stored_data.get(config_entry.entry_id, [])
    }

    added_macs = set()

    async def async_update_data():
        """Fetch latest data and update known devices."""
        try:
            online_devices = await api.get_online_list()

            normalized_devices = []
            for dev in online_devices:
                dev_copy = dev.copy()
                dev_copy["dev_mac"] = normalize_mac(dev["dev_mac"])
                normalized_devices.append(dev_copy)

            current_macs = {dev["dev_mac"] for dev in normalized_devices}
            new_macs = current_macs - known_macs

            if new_macs:
                known_macs.update(new_macs)
                stored_data[config_entry.entry_id] = list(known_macs)
                await store.async_save(stored_data)

            return {"online": normalized_devices, "known_macs": known_macs.copy()}

        except APIError as e:
            _LOGGER.warning("API error: %s", str(e))
            return {"online": [], "known_macs": known_macs.copy()}

    coordinator = TwibiCoordinator(
        hass,
        _LOGGER,
        name="twibi_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=config_entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    entities = []
    for mac in coordinator.data.get("known_macs", set()):
        if mac not in added_macs:
            device_info = next(
                (dev for dev in coordinator.data.get("online", []) if dev["dev_mac"] == mac),
                {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
            )
            entities.append(
                TwibiDeviceTracker(
                    coordinator,
                    host,
                    mac,
                    device_info,
                    config_entry.entry_id
                )
            )
            added_macs.add(mac)

    if entities:
        async_add_entities(entities)

    @callback
    def async_check_for_new_devices():
        """Check for new known MACs and create entities."""
        known_macs_set = coordinator.data.get("known_macs", set())
        new_macs = known_macs_set - added_macs

        if new_macs:
            new_entities = []
            for mac in new_macs:
                device_info = next(
                    (dev for dev in coordinator.data.get("online", []) if dev["dev_mac"] == mac),
                    {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
                )
                new_entities.append(
                    TwibiDeviceTracker(
                        coordinator,
                        host,
                        mac,
                        device_info,
                        config_entry.entry_id
                    )
                )
                added_macs.add(mac)

            async_add_entities(new_entities)

    coordinator.async_add_listener(async_check_for_new_devices)


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
            "name": device_info.get("dev_name") or f"Device {mac}",
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
            self._device_info.get("dev_name")
            or f"Device {self._device_info.get('dev_ip', self._mac)}"
        )

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        return self._mac in {dev["dev_mac"] for dev in self.coordinator.data.get("online", [])}

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device, or None if unavailable."""
        current_info = next(
            (dev for dev in self.coordinator.data.get("online", []) if dev["dev_mac"] == self._mac),
            self._device_info,
        )
        return current_info.get("dev_ip")

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes for the device."""
        current_info = next(
            (dev for dev in self.coordinator.data.get("online", []) if dev["dev_mac"] == self._mac),
            self._device_info,
        )
        connection_type = current_info.get("wifi_mode", "--")
        return {
            "ip": current_info.get("dev_ip"),
            "mac": self._mac,
            "rssi": current_info.get("rssi"),
            "tx_rate": current_info.get("tx_rate"),
            "connection": "Ethernet" if connection_type == "--" else connection_type
        }
