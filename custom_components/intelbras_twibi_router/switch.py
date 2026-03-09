"""Switch platform for Twibi Router integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.enums import GuestNetworkBandwidthLimit, GuestNetworkTimeRestriction
from .coordinator import TwibiCoordinator
from .helpers import build_router_device_info
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router switch entities."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    async_add_entities(
        [
            TwibiGuestNetworkSwitch(coordinator, primary_device_identifier),
            TwibiUpnpSwitch(coordinator, primary_device_identifier),
        ]
    )


class TwibiBaseSwitch(SwitchEntity):
    """Base class for Twibi Router switches."""

    coordinator: TwibiCoordinator

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        switch_type: str,
        name: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_should_poll = False
        self._attr_available = coordinator.last_update_success
        self._attr_device_info = build_router_device_info(device_identifier)
        self._attr_name = name
        self._attr_unique_id = f"{device_identifier}_{switch_type}"

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh entity state when coordinator data changes."""
        self._update_from_coordinator()
        self.async_write_ha_state()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh cached attributes from coordinator data."""
        self._attr_available = self.coordinator.last_update_success


class TwibiGuestNetworkSwitch(TwibiBaseSwitch):
    """Guest network switch."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the switch."""
        super().__init__(
            coordinator,
            device_identifier,
            "guest_network",
            "Guest Network",
        )
        self._attr_icon = "mdi:wifi-plus"
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh guest network state from coordinator data."""
        guest_info = self.coordinator.data.guest_info
        self._attr_available = (
            self.coordinator.last_update_success and guest_info is not None
        )
        self._attr_is_on = bool(guest_info and guest_info.enabled)
        self._attr_extra_state_attributes = (
            {
                "ssid": guest_info.ssid,
                "password_set": bool(guest_info.password),
                "time_restriction": guest_info.time_restriction,
                "bandwidth_limit": (
                    "No limit"
                    if guest_info.bandwidth_limit == GuestNetworkBandwidthLimit.UNLIMITED
                    else guest_info.bandwidth_limit
                ),
            }
            if guest_info is not None
            else {}
        )

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


class TwibiUpnpSwitch(TwibiBaseSwitch):
    """UPnP switch."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, device_identifier, "upnp", "UPnP")
        self._attr_icon = "mdi:router-network"
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh UPnP state from coordinator data."""
        upnp_info = self.coordinator.data.upnp_info
        self._attr_available = (
            self.coordinator.last_update_success and upnp_info is not None
        )
        self._attr_is_on = bool(upnp_info and upnp_info.upnp_enabled)
        self._attr_extra_state_attributes = {}

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
