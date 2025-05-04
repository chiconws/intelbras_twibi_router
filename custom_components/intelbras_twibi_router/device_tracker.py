"""Device tracker for Twibi Router integration."""

from datetime import timedelta
import logging

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
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
    """Normalize MAC address to colon-separated lowercase."""
    mac = mac.lower().replace("-", "").replace(":", "").strip()
    return ":".join(mac[i:i+2] for i in range(0, 12, 2))


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up device tracker dynamically."""
    host = config_entry.data[CONF_TWIBI_IP_ADDRESS]
    session = async_get_clientsession(hass)

    twibi = TwibiAPI(
        host,
        config_entry.data[CONF_PASSWORD],
        config_entry.data[CONF_EXCLUDE_WIRED],
        config_entry.data[CONF_UPDATE_INTERVAL],
        session
    )

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored_data = await store.async_load() or {}

    # Normalize stored MACs
    known_macs = {
        normalize_mac(mac)
        for mac in stored_data.get(config_entry.entry_id, [])
    }

    added_macs = set()

    async def async_update_data():
        """Fetch latest data and update known devices."""
        try:
            online_devices = await twibi.get_online_list()

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
                _LOGGER.debug("Added new MACs: %s", new_macs)

            return {"online": normalized_devices, "known_macs": known_macs.copy()}

        except Exception:
            _LOGGER.exception("Error updating data")
            return {"online": [], "known_macs": known_macs.copy()}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="twibi_devices",
        update_method=async_update_data,
        update_interval=timedelta(seconds=config_entry.data[CONF_UPDATE_INTERVAL]),
    )

    await coordinator.async_config_entry_first_refresh()

    initial_entities = []
    for mac in coordinator.data.get("known_macs", set()):
        if mac not in added_macs:
            device_info = next(
                (dev for dev in coordinator.data.get("online", []) if dev["dev_mac"] == mac),
                {"dev_mac": mac, "dev_name": f"Device {mac}", "dev_ip": None},
            )
            initial_entities.append(
                TwibiDeviceTracker(
                    coordinator,
                    host,
                    mac,
                    device_info,
                    config_entry.entry_id
                )
            )
            added_macs.add(mac)
            _LOGGER.debug("Initial entity created for MAC: %s", mac)

    if initial_entities:
        async_add_entities(initial_entities)

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
        """Initialize the TwibiDeviceTracker.

        Args:
            coordinator: The data update coordinator for managing updates.
            host: The host address of the Twibi router.
            mac: The MAC address of the tracked device.
            device_info: A dictionary containing device information.
            entry_id: Config entry ID for device registry.

        """
        super().__init__(coordinator)
        self._mac = mac
        self._host = host
        self._entry_id = entry_id
        self._device_info = device_info
        self._attr_entity_category = None
        self._attr_should_poll = False

        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "connections": {(CONNECTION_NETWORK_MAC, mac)},
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

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.last_update_success
