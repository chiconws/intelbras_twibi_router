"""Device tracker for Twibi Router integration."""

from datetime import timedelta
import logging

from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
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
STORAGE_KEY = f"{DOMAIN}.storage"
STORAGE_VERSION = 1

def normalize_mac(mac: str) -> str:
    """Normalize MAC address to lowercase without colons."""
    return mac.lower().replace(":", "").replace("-", "").strip()

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

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    # Normalize stored MACs
    known_macs = {
        normalize_mac(mac)
        for mac in stored_data.get(config_entry.entry_id, [])
    }

    # Track which MACs have been added as entities
    added_macs = set()

    async def async_update_data():
        """Fetch latest data and update known devices."""
        try:
            online_devices = await twibi.get_online_list()

            # Normalize MACs from API response
            normalized_devices = []
            for dev in online_devices:
                dev = dev.copy()
                dev["dev_mac"] = normalize_mac(dev["dev_mac"])
                normalized_devices.append(dev)

            current_macs = {dev["dev_mac"] for dev in normalized_devices}
            new_macs = current_macs - known_macs

            if new_macs:
                known_macs.update(new_macs)
                stored_data[config_entry.entry_id] = list(known_macs)
                await store.async_save(stored_data)
                _LOGGER.debug("Added new MACs: %s", new_macs)

            return {"online": normalized_devices, "known_macs": known_macs.copy()}

        except Exception as err:
            _LOGGER.error("Error updating data: %s", err, exc_info=True)
            return {"online": [], "known_macs": known_macs.copy()}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=twibi.update_interval),
    )

    # Force initial refresh
    await coordinator.async_config_entry_first_refresh()

    # Create initial entities for all known MACs
    initial_entities = []
    for mac in coordinator.data.get("known_macs", set()):
        if mac not in added_macs:
            device_info = next(
                (dev for dev in coordinator.data.get("online", []) if dev["dev_mac"] == mac),
                {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
            )
            initial_entities.append(TwibiDeviceTracker(coordinator, mac, device_info))
            added_macs.add(mac)
            _LOGGER.debug("Initial entity created for MAC: %s", mac)

    if initial_entities:
        async_add_entities(initial_entities)

    @callback
    def async_check_for_new_devices():
        """Check for new known MACs and create entities."""
        known_macs = coordinator.data.get("known_macs", set())
        new_macs = known_macs - added_macs

        if new_macs:
            new_entities = []
            for mac in new_macs:
                # Find device info or create placeholder
                device_info = next(
                    (dev for dev in coordinator.data.get("online", []) if dev["dev_mac"] == mac),
                    {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
                )
                new_entities.append(TwibiDeviceTracker(coordinator, mac, device_info))
                added_macs.add(mac)
                _LOGGER.debug("New entity created for MAC: %s", mac)

            async_add_entities(new_entities)

    # Listen for coordinator updates to add new entities
    coordinator.async_add_listener(async_check_for_new_devices)

class TwibiDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Representation of a Twibi-connected device."""

    def __init__(self, coordinator, mac: str, device_info: dict) -> None:
        """Initialize the Twibi device tracker.

        Args:
            coordinator: The data update coordinator for managing updates.
            mac: The MAC address of the device.
            device_info: A dictionary containing device information.

        """
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
            or f"Device {self._device_info.get('dev_ip', self._mac)}"
        )

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected."""
        online_macs = {dev["dev_mac"] for dev in self.coordinator.data.get("online", [])}
        return self._mac in online_macs

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
        conn = current_info.get("wifi_mode", "--")
        return {
            "ip": current_info.get("dev_ip"),
            "mac": self._mac,
            "rssi": current_info.get("rssi"),
            "tx_rate": current_info.get("tx_rate"),
            "connection": "Ethernet" if conn == "--" else conn
        }
