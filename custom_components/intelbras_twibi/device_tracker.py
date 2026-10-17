"""Device trackers: one per client of the mesh."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Client
from .const import CONF_TRACKED_DEVICES, CONF_WIFI_ONLY
from .coordinator import TwibiConfigEntry, TwibiCoordinator

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Track the chosen clients, or every client seen if none were chosen."""
    coordinator = entry.runtime_data
    selected: list[str] = entry.options.get(CONF_TRACKED_DEVICES, [])
    wifi_only: bool = entry.options.get(CONF_WIFI_ONLY, False)
    known: set[str] = set()

    @callback
    def add_new() -> None:
        if selected:
            wanted = set(selected)
        else:
            wanted = {
                mac
                for mac, client in coordinator.data.clients.items()
                if not (wifi_only and client.band == "wired")
            }
            if not known:  # first run: keep trackers created in earlier sessions
                registry = er.async_get(hass)
                wanted |= {
                    e.unique_id
                    for e in er.async_entries_for_config_entry(registry, entry.entry_id)
                    if e.domain == "device_tracker"
                }
        if new := wanted - known:
            known.update(new)
            async_add_entities(TwibiTracker(coordinator, mac, bool(selected)) for mac in sorted(new))

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class TwibiTracker(CoordinatorEntity[TwibiCoordinator], ScannerEntity):
    """Home when the client shows up in the router's online list."""

    def __init__(self, coordinator: TwibiCoordinator, mac: str, chosen: bool) -> None:
        """Track one MAC address."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._chosen = chosen
        client = coordinator.data.clients.get(mac)
        self._attr_name = (client.name if client else "") or mac

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Enable clients the user picked; others follow Home Assistant's default."""
        return self._chosen or super().entity_registry_enabled_default

    @property
    def _client(self) -> Client | None:
        return self.coordinator.data.clients.get(self._attr_mac_address)

    @property
    def is_connected(self) -> bool:
        """Return whether the client is online."""
        return self._client is not None

    @property
    def ip_address(self) -> str | None:
        """Return the client's current IP."""
        client = self._client
        return client.ip if client else None

    @property
    def hostname(self) -> str | None:
        """Return the name the router knows."""
        client = self._client
        return client.name if client and client.name else None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Expose how the client is connected."""
        client = self._client
        return {"connection": client.band} if client else {}


