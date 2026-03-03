"""Controller for Twibi Router device actions."""

import logging
from typing import Any

from .connection import APIError, TwibiConnection
from .enums import (
    GuestNetworkBandwidthLimit,
    GuestNetworkState,
    GuestNetworkTimeRestriction,
    NodeLedState,
    UpnpState,
    WifiSecurityMode,
    WifiSecurityType,
)
from .models import CommandResult

_LOGGER = logging.getLogger(__name__)


class TwibiController:
    """Handles device control actions for Twibi Router."""

    def __init__(self, connection: TwibiConnection) -> None:
        """Initialize the controller."""
        self.connection = connection

    def _build_payload(
        self,
        command: str,
        values: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Build a command payload with the required router timestamp."""
        return {
            command: {
                **values,
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

    async def _execute_command(
        self,
        action: str,
        payload: dict[str, Any],
    ) -> CommandResult:
        """Send a command and return a typed result."""
        try:
            result = await self.connection.send_command(payload)
        except APIError as err:
            _LOGGER.error("Failed to %s: %s", action, err)
            return CommandResult.from_error(next(iter(payload), "unknown"), str(err))

        if result.rejected_by_router:
            _LOGGER.error(
                "Router rejected %s command (%s): %s",
                action,
                result.errcode,
                result.raw,
            )

        return result

    async def set_led_status_result(self, serial: str, enabled: bool) -> CommandResult:
        """Set LED status for a specific node and return a typed result."""
        payload = self._build_payload(
            "led",
            {
                "led_en": NodeLedState.ON if enabled else NodeLedState.OFF,
                "sn": serial,
            },
        )

        result = await self._execute_command(f"set LED status for {serial}", payload)
        if result.success:
            _LOGGER.debug("LED status set for %s: %s", serial, enabled)
        return result

    async def set_led_status(self, serial: str, enabled: bool) -> bool:
        """Set LED status for a specific node."""
        result = await self.set_led_status_result(serial, enabled)
        return result.success

    async def restart_router_result(self) -> CommandResult:
        """Restart the router and return a typed result."""
        payload = self._build_payload(
            "sys_reboot",
            {
                "action": "reboot",
            },
        )

        result = await self._execute_command("restart router", payload)
        if result.success:
            _LOGGER.info("Router restart command sent successfully")
        return result

    async def restart_router(self) -> bool:
        """Restart the router."""
        result = await self.restart_router_result()
        return result.success

    async def set_wifi_config_result(
        self,
        ssid: str,
        password: str,
        security_type: WifiSecurityType = WifiSecurityType.AES,
        security_mode: WifiSecurityMode = WifiSecurityMode.PSK_PSK2,
    ) -> CommandResult:
        """Set WiFi configuration and return a typed result."""
        payload = self._build_payload(
            "wifi",
            {
                "ssid": ssid,
                "pass": password,
                "type": security_type,
                "security": security_mode,
            },
        )

        result = await self._execute_command("set WiFi configuration", payload)
        if result.success:
            _LOGGER.debug("WiFi configuration updated")
        return result

    async def set_wifi_config(
        self,
        ssid: str,
        password: str,
        security_type: WifiSecurityType = WifiSecurityType.AES,
        security_mode: WifiSecurityMode = WifiSecurityMode.PSK_PSK2,
    ) -> bool:
        """Set WiFi configuration."""
        result = await self.set_wifi_config_result(
            ssid,
            password,
            security_type,
            security_mode,
        )
        return result.success

    async def set_guest_network_result(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: GuestNetworkTimeRestriction = GuestNetworkTimeRestriction.ALWAYS,
        bandwidth_limit: GuestNetworkBandwidthLimit = GuestNetworkBandwidthLimit.UNLIMITED,
    ) -> CommandResult:
        """Configure guest network settings and return a typed result."""
        payload = self._build_payload(
            "guest_info",
            {
                "guest_en": (
                    GuestNetworkState.ENABLED
                    if enabled
                    else GuestNetworkState.DISABLED
                ),
                "guest_time": time_restriction,
                "limit": bandwidth_limit,
            },
        )

        # Always include SSID and password to match web UI format exactly
        # Use empty string if not provided, just like the web UI does
        payload["guest_info"]["guest_ssid"] = ssid if ssid else ""
        payload["guest_info"]["guest_pass"] = password if password else ""

        _LOGGER.info(
            "Guest network API payload: %s",
            {
                key: "***" if key == "guest_pass" else value
                for key, value in payload["guest_info"].items()
            },
        )

        result = await self._execute_command("set guest network", payload)
        if result.success:
            _LOGGER.info("Guest network configuration command sent successfully")
        return result

    async def set_guest_network(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: GuestNetworkTimeRestriction = GuestNetworkTimeRestriction.ALWAYS,
        bandwidth_limit: GuestNetworkBandwidthLimit = GuestNetworkBandwidthLimit.UNLIMITED,
    ) -> bool:
        """Configure guest network settings."""
        result = await self.set_guest_network_result(
            enabled,
            ssid,
            password,
            time_restriction,
            bandwidth_limit,
        )
        return result.success

    async def set_upnp_status_result(self, enabled: bool) -> CommandResult:
        """Enable or disable UPnP and return a typed result."""
        payload = self._build_payload(
            "upnp_info",
            {
                "upnp_en": (
                    UpnpState.ENABLED
                    if enabled
                    else UpnpState.DISABLED
                ),
            },
        )

        result = await self._execute_command("set UPnP status", payload)
        if result.success:
            _LOGGER.debug("UPnP status set to: %s", enabled)
        return result

    async def set_upnp_status(self, enabled: bool) -> bool:
        """Enable or disable UPnP."""
        result = await self.set_upnp_status_result(enabled)
        return result.success
