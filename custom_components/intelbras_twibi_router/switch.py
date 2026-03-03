"""Switch platform for Twibi Router integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.enums import GuestNetworkBandwidthLimit, GuestNetworkTimeRestriction
from .const import DOMAIN
from .coordinator import TwibiCoordinator

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
    if coordinator.data.guest_info is not None:
        entities.append(TwibiGuestNetworkSwitch(coordinator, host))

    # UPnP switch
    if coordinator.data.upnp_info is not None:
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
        sw_version = primary_node.device_version if primary_node else None

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
        guest_info = self.coordinator.data.guest_info
        return bool(guest_info and guest_info.enabled)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        guest_info = self.coordinator.data.guest_info
        if guest_info is None:
            return {}

        password = guest_info.password
        bandwidth_limit = guest_info.bandwidth_limit

        return {
            "ssid": guest_info.ssid,
            "password_set": bool(password),
            "time_restriction": guest_info.time_restriction,
            "bandwidth_limit": (
                "No limit"
                if bandwidth_limit == GuestNetworkBandwidthLimit.UNLIMITED
                else bandwidth_limit
            ),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on guest network."""
        api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]

        guest_info = self.coordinator.data.guest_info
        current_ssid = guest_info.ssid if guest_info else ""
        current_password = guest_info.password if guest_info else ""
        current_time = (
            guest_info.time_restriction
            if guest_info
            else GuestNetworkTimeRestriction.ALWAYS
        )
        current_limit = (
            guest_info.bandwidth_limit
            if guest_info
            else GuestNetworkBandwidthLimit.UNLIMITED
        )

        _LOGGER.info(
            "Guest WiFi turn ON - Current settings: SSID='%s', Password='%s', Time='%s', Limit='%s'",
            current_ssid,
            "***" if current_password else "None",
            current_time,
            current_limit,
        )

        success = await api.set_guest_network(
            enabled=True,
            ssid=current_ssid if current_ssid else None,
            password=current_password if current_password else None,
            time_restriction=current_time,
            bandwidth_limit=current_limit,
        )

        _LOGGER.info("Guest WiFi turn ON - API call result: %s", success)

        if not success:
            _LOGGER.error("Failed to enable guest network")
            return

        await self.coordinator.async_refresh()
        new_guest_info = self.coordinator.data.guest_info
        new_enabled = bool(new_guest_info and new_guest_info.enabled)
        _LOGGER.info("Guest WiFi turn ON - After refresh, enabled state: %s", new_enabled)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off guest network."""
        api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]

        guest_info = self.coordinator.data.guest_info
        current_ssid = guest_info.ssid if guest_info else ""
        current_password = guest_info.password if guest_info else ""
        current_time = (
            guest_info.time_restriction
            if guest_info
            else GuestNetworkTimeRestriction.ALWAYS
        )
        current_limit = (
            guest_info.bandwidth_limit
            if guest_info
            else GuestNetworkBandwidthLimit.UNLIMITED
        )

        _LOGGER.info(
            "Guest WiFi turn OFF - Current settings: SSID='%s', Password='%s', Time='%s', Limit='%s'",
            current_ssid,
            "***" if current_password else "None",
            current_time,
            current_limit,
        )

        success = await api.set_guest_network(
            enabled=False,
            ssid=current_ssid if current_ssid else None,
            password=current_password if current_password else None,
            time_restriction=current_time,
            bandwidth_limit=current_limit,
        )

        _LOGGER.info("Guest WiFi turn OFF - API call result: %s", success)

        if not success:
            _LOGGER.error("Failed to disable guest network")
            return

        await self.coordinator.async_refresh()
        new_guest_info = self.coordinator.data.guest_info
        new_enabled = bool(new_guest_info and new_guest_info.enabled)
        _LOGGER.info("Guest WiFi turn OFF - After refresh, enabled state: %s", new_enabled)


class TwibiUpnpSwitch(TwibiBaseSwitch):
    """UPnP switch."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, host, "upnp", "UPnP")
        self._attr_icon = "mdi:router-network"

    @property
    def is_on(self) -> bool:
        """Return true if UPnP is enabled."""
        upnp_info = self.coordinator.data.upnp_info
        return bool(upnp_info and upnp_info.upnp_enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on UPnP."""
        api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]
        success = await api.set_upnp(enabled=True)
        if not success:
            _LOGGER.error("Failed to enable UPnP")
            return

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off UPnP."""
        api = self.coordinator.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]["api"]
        success = await api.set_upnp(enabled=False)
        if not success:
            _LOGGER.error("Failed to disable UPnP")
            return

        await self.coordinator.async_refresh()
