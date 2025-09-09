"""Controller for Twibi Router device actions."""

import logging

from .connection import TwibiConnection

_LOGGER = logging.getLogger(__name__)


class TwibiController:
    """Handles device control actions for Twibi Router."""

    def __init__(self, connection: TwibiConnection) -> None:
        """Initialize the controller."""
        self.connection = connection

    async def set_led_status(self, serial: str, enabled: bool) -> bool:
        """Set LED status for a specific node."""
        payload = {
            "led": {
                "led_en": "1" if enabled else "0",
                "sn": serial,
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

        try:
            await self.connection.send_command(payload)
            _LOGGER.debug("LED status set for %s: %s", serial, enabled)
        except Exception as err:
            _LOGGER.error("Failed to set LED status for %s: %s", serial, err)
            return False

        return True

    async def restart_router(self) -> bool:
        """Restart the router."""
        payload = {
            "sys_reboot": {
                "action": "reboot",
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

        try:
            await self.connection.send_command(payload)
            _LOGGER.info("Router restart command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to restart router: %s", err)
            return False

        return True

    async def set_wifi_config(
        self,
        ssid: str,
        password: str,
        security_type: str = "aes",
        security_mode: str = "psk psk2"
    ) -> bool:
        """Set WiFi configuration."""
        payload = {
            "wifi": {
                "ssid": ssid,
                "pass": password,
                "type": security_type,
                "security": security_mode,
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

        try:
            await self.connection.send_command(payload)
            _LOGGER.debug("WiFi configuration updated")
        except Exception as err:
            _LOGGER.error("Failed to set WiFi configuration: %s", err)
            return False

        return True

    async def set_guest_network(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: str = "always",
        bandwidth_limit: str = "0"
    ) -> bool:
        """Configure guest network settings."""
        payload = {
            "guest_info": {
                "guest_en": "1" if enabled else "0",
                "guest_time": time_restriction,
                "limit": bandwidth_limit,
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

        # Always include SSID and password to match web UI format exactly
        # Use empty string if not provided, just like the web UI does
        payload["guest_info"]["guest_ssid"] = ssid if ssid else ""
        payload["guest_info"]["guest_pass"] = password if password else ""

        _LOGGER.info("Guest network API payload: %s", {k: "***" if k == "guest_pass" else v for k, v in payload["guest_info"].items()})

        try:
            await self.connection.send_command(payload)
            _LOGGER.info("Guest network configuration command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to set guest network configuration: %s", err)
            return False

        return True

    async def set_upnp_status(self, enabled: bool) -> bool:
        """Enable or disable UPnP."""
        payload = {
            "upnp_info": {
                "upnp_en": "1" if enabled else "0",
                "timestamp": str(self.connection.get_timestamp()),
            }
        }

        try:
            await self.connection.send_command(payload)
            _LOGGER.debug("UPnP status set to: %s", enabled)
        except Exception as err:
            _LOGGER.error("Failed to set UPnP status: %s", err)
            return False

        return True
