"""Switch platform for Twibi Router integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api.enums import GuestNetworkBandwidthLimit, GuestNetworkTimeRestriction
from .coordinator import TwibiCoordinator
from .const import DOMAIN
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router switch entities."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator: TwibiCoordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    entities = []

    # Create optional switches unconditionally so transient startup failures
    # do not permanently suppress entities until the next reload.
    entities.append(TwibiGuestNetworkSwitch(coordinator, primary_device_identifier))
    entities.append(TwibiUpnpSwitch(coordinator, primary_device_identifier))

    # Remote web access switch removed per user request

    async_add_entities(entities)


class TwibiBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for Twibi Router switches."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        switch_type: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_identifier = device_identifier
        self._switch_type = switch_type
        self._attr_name = name
        self._attr_unique_id = f"{device_identifier}_{switch_type}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_identifier)}}


class TwibiGuestNetworkSwitch(TwibiBaseSwitch):
    """Guest network switch."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_identifier, "guest_network", "Guest Network")
        self._attr_icon = "mdi:wifi-plus"

    @property
    def is_on(self) -> bool:
        """Return true if guest network is enabled."""
        guest_info = self.coordinator.data.guest_info
        return bool(guest_info and guest_info.enabled)

    @property
    def available(self) -> bool:
        """Return whether guest network data is currently available."""
        return self.coordinator.last_update_success and self.coordinator.data.guest_info is not None

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

        success = await self.coordinator.api.set_guest_network(
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

        success = await self.coordinator.api.set_guest_network(
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

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_identifier, "upnp", "UPnP")
        self._attr_icon = "mdi:router-network"

    @property
    def is_on(self) -> bool:
        """Return true if UPnP is enabled."""
        upnp_info = self.coordinator.data.upnp_info
        return bool(upnp_info and upnp_info.upnp_enabled)

    @property
    def available(self) -> bool:
        """Return whether UPnP data is currently available."""
        return self.coordinator.last_update_success and self.coordinator.data.upnp_info is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on UPnP."""
        success = await self.coordinator.api.set_upnp(enabled=True)
        if not success:
            _LOGGER.error("Failed to enable UPnP")
            return

        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off UPnP."""
        success = await self.coordinator.api.set_upnp(enabled=False)
        if not success:
            _LOGGER.error("Failed to disable UPnP")
            return

        await self.coordinator.async_refresh()
