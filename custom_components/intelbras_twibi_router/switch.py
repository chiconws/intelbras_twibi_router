"""Switch platform for Twibi Router integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator_v2 import TwibiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router switch entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TwibiCoordinator = entry_data["coordinator"]
    host = entry_data["host"]

    entities = []

    # Guest network switch
    if coordinator.data.get("guest_info"):
        entities.append(TwibiGuestNetworkSwitch(coordinator, host))

    # UPnP switch
    if coordinator.data.get("upnp_info"):
        entities.append(TwibiUpnpSwitch(coordinator, host))

    # Remote web access switch removed per user request

    async_add_entities(entities)


class TwibiBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Twibi Router switches."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        host: str,
        switch_type: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._host = host
        self._switch_type = switch_type
        self._attr_name = name
        self._attr_unique_id = f"{host}_{switch_type}"

        # Get firmware version from primary node
        primary_node = coordinator.get_primary_node()
        sw_version = primary_node.get("dut_version") if primary_node else None

        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"Twibi Router {host}",
            "manufacturer": "Intelbras",
            "model": "Twibi Router",
            "sw_version": sw_version,
        }


class TwibiGuestNetworkSwitch(TwibiBaseSwitch):
    """Guest network switch."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, host, "guest_network", "Guest Network")
        self._attr_icon = "mdi:wifi-plus"

    @property
    def is_on(self) -> bool:
        """Return true if guest network is enabled."""
        guest_info = self.coordinator.data.get("guest_info", {})
        return guest_info.get("guest_en", "0") == "1"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        guest_info = self.coordinator.data.get("guest_info", {})
        password = guest_info.get("guest_pass", "")
        bandwidth_limit = guest_info.get("limit", "0")

        return {
            "ssid": guest_info.get("guest_ssid", ""),
            "password": password if password else "NO PASSWORD",
            "time_restriction": guest_info.get("guest_time", ""),
            "bandwidth_limit": "No limit" if bandwidth_limit == "0" else bandwidth_limit,
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on guest network."""
        try:
            api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]

            # Get current guest network settings to preserve SSID and password
            guest_info = self.coordinator.data.get("guest_info", {})
            current_ssid = guest_info.get("guest_ssid", "")
            current_password = guest_info.get("guest_pass", "")
            current_time = guest_info.get("guest_time", "always")
            current_limit = guest_info.get("limit", "0")

            _LOGGER.info("Guest WiFi turn ON - Current settings: SSID='%s', Password='%s', Time='%s', Limit='%s'",
                        current_ssid, "***" if current_password else "None", current_time, current_limit)

            success = await api.set_guest_network(
                enabled=True,
                ssid=current_ssid if current_ssid else None,
                password=current_password if current_password else None,
                time_restriction=current_time,
                bandwidth_limit=current_limit
            )

            _LOGGER.info("Guest WiFi turn ON - API call result: %s", success)

            if success:
                await self.coordinator.async_refresh()
                # Check if the change was applied
                new_guest_info = self.coordinator.data.get("guest_info", {})
                new_enabled = new_guest_info.get("guest_en", "0") == "1"
                _LOGGER.info("Guest WiFi turn ON - After refresh, enabled state: %s", new_enabled)
            else:
                _LOGGER.error("Failed to enable guest network")
        except Exception as err:
            _LOGGER.error("Error enabling guest network: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off guest network."""
        try:
            api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]

            # Get current guest network settings to preserve SSID and password
            guest_info = self.coordinator.data.get("guest_info", {})
            current_ssid = guest_info.get("guest_ssid", "")
            current_password = guest_info.get("guest_pass", "")
            current_time = guest_info.get("guest_time", "always")
            current_limit = guest_info.get("limit", "0")

            _LOGGER.info("Guest WiFi turn OFF - Current settings: SSID='%s', Password='%s', Time='%s', Limit='%s'",
                        current_ssid, "***" if current_password else "None", current_time, current_limit)

            success = await api.set_guest_network(
                enabled=False,
                ssid=current_ssid if current_ssid else None,
                password=current_password if current_password else None,
                time_restriction=current_time,
                bandwidth_limit=current_limit
            )

            _LOGGER.info("Guest WiFi turn OFF - API call result: %s", success)

            if success:
                await self.coordinator.async_refresh()
                # Check if the change was applied
                new_guest_info = self.coordinator.data.get("guest_info", {})
                new_enabled = new_guest_info.get("guest_en", "0") == "1"
                _LOGGER.info("Guest WiFi turn OFF - After refresh, enabled state: %s", new_enabled)
            else:
                _LOGGER.error("Failed to disable guest network")
        except Exception as err:
            _LOGGER.error("Error disabling guest network: %s", err)


class TwibiUpnpSwitch(TwibiBaseSwitch):
    """UPnP switch."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, host, "upnp", "UPnP")
        self._attr_icon = "mdi:router-network"

    @property
    def is_on(self) -> bool:
        """Return true if UPnP is enabled."""
        upnp_info = self.coordinator.data.get("upnp_info", {})
        return upnp_info.get("upnp_en", "0") == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on UPnP."""
        try:
            api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]
            success = await api.set_upnp(enabled=True)
            if success:
                await self.coordinator.async_refresh()
            else:
                _LOGGER.error("Failed to enable UPnP")
        except Exception as err:
            _LOGGER.error("Error enabling UPnP: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off UPnP."""
        try:
            api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]
            success = await api.set_upnp(enabled=False)
            if success:
                await self.coordinator.async_refresh()
            else:
                _LOGGER.error("Failed to disable UPnP")
        except Exception as err:
            _LOGGER.error("Error disabling UPnP: %s", err)
