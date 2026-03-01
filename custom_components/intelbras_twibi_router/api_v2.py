"""Improved API module for interacting with Twibi Router."""

import logging
from typing import Any

import aiohttp

from .api import APIError, TwibiConnection, TwibiController, TwibiDataFetcher
from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class TwibiAPI:
    """Improved Twibi Router API class with better architecture."""

    def __init__(
        self,
        host: str,
        password: str,
        exclude_wired: bool,
        update_interval: int,
        session: aiohttp.ClientSession,
        timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the Twibi Router API."""
        self.host = host
        self.exclude_wired = exclude_wired
        self.update_interval = update_interval

        # Initialize the new API components
        self._connection = TwibiConnection(host, password, session, timeout)
        self._data_fetcher = TwibiDataFetcher(self._connection, exclude_wired)
        self._controller = TwibiController(self._connection)

    @property
    def connection(self) -> TwibiConnection:
        """Get the connection manager."""
        return self._connection

    @property
    def data_fetcher(self) -> TwibiDataFetcher:
        """Get the data fetcher."""
        return self._data_fetcher

    @property
    def controller(self) -> TwibiController:
        """Get the controller."""
        return self._controller

    # Backward compatibility methods
    async def login(self) -> bool:
        """Login to router (backward compatibility)."""
        try:
            await self._connection.ensure_authenticated()
        except Exception:
            return False

        return True

    async def get_modules(self, module_list: list[str]) -> dict[str, Any]:
        """Retrieve module data from the router (backward compatibility)."""
        return await self._data_fetcher.get_all_data(module_list)

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get the HTTP session (backward compatibility)."""
        return self._connection.session

    @property
    def base_url(self) -> str:
        """Return base URL (backward compatibility)."""
        return self._connection.base_url

    @property
    def get_url(self) -> str:
        """Return get URL (backward compatibility)."""
        return self._connection.get_url

    @property
    def set_url(self) -> str:
        """Return set URL (backward compatibility)."""
        return self._connection.set_url

    @staticmethod
    def get_timestamp() -> int:
        """Get current timestamp in milliseconds (backward compatibility)."""
        return TwibiConnection.get_timestamp()

    # Enhanced methods using new architecture
    async def get_node_info(self) -> list[dict[str, Any]]:
        """Get node information with improved error handling."""
        try:
            nodes = await self._data_fetcher.get_node_info()
            return [node.to_dict() for node in nodes]
        except Exception as err:
            _LOGGER.error("Failed to get node info: %s", err)
            raise APIError(f"Failed to get node info: {err}") from err

    async def get_online_devices(self) -> list[dict[str, Any]]:
        """Get online devices with improved filtering."""
        try:
            devices = await self._data_fetcher.get_online_devices()
            return [device.to_dict() for device in devices]
        except Exception as err:
            _LOGGER.error("Failed to get online devices: %s", err)
            raise APIError(f"Failed to get online devices: {err}") from err

    async def get_wan_statistics(self) -> list[dict[str, Any]]:
        """Get WAN statistics with improved data handling."""
        try:
            stats = await self._data_fetcher.get_wan_statistics()
            return [stat.to_dict() for stat in stats]
        except Exception as err:
            _LOGGER.error("Failed to get WAN statistics: %s", err)
            raise APIError(f"Failed to get WAN statistics: {err}") from err

    async def set_led_status(self, serial: str, enabled: bool) -> bool:
        """Set LED status for a node."""
        return await self._controller.set_led_status(serial, enabled)

    async def restart_router(self) -> bool:
        """Restart the router."""
        return await self._controller.restart_router()

    async def set_wifi_config(
        self,
        ssid: str,
        password: str,
        security_type: str = "aes",
        security_mode: str = "psk psk2"
    ) -> bool:
        """Set WiFi configuration."""
        return await self._controller.set_wifi_config(
            ssid, password, security_type, security_mode
        )

    async def set_guest_network(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: str = "always",
        bandwidth_limit: str = "0"
    ) -> bool:
        """Configure guest network."""
        return await self._controller.set_guest_network(
            enabled, ssid, password, time_restriction, bandwidth_limit
        )

    async def set_upnp(self, enabled: bool) -> bool:
        """Enable or disable UPnP."""
        return await self._controller.set_upnp_status(enabled)

    async def get_device_by_mac(self, mac: str) -> dict[str, Any] | None:
        """Get specific device by MAC address."""
        try:
            device = await self._data_fetcher.get_device_by_mac(mac)
            return device.to_dict() if device else None
        except Exception as err:
            _LOGGER.error("Failed to get device by MAC %s: %s", mac, err)
            return None

    async def get_primary_node(self) -> dict[str, Any] | None:
        """Get the primary router node."""
        try:
            node = await self._data_fetcher.get_primary_node()
            return node.to_dict() if node else None
        except Exception as err:
            _LOGGER.error("Failed to get primary node: %s", err)
            return None

    async def get_secondary_nodes(self) -> list[dict[str, Any]]:
        """Get all secondary router nodes."""
        try:
            nodes = await self._data_fetcher.get_secondary_nodes()
            return [node.to_dict() for node in nodes]
        except Exception as err:
            _LOGGER.error("Failed to get secondary nodes: %s", err)
            return []

    def invalidate_auth(self) -> None:
        """Invalidate current authentication state."""
        self._connection.invalidate_auth()

    async def health_check(self) -> bool:
        """Perform a health check on the API connection."""
        try:
            await self._connection.ensure_authenticated()
            # Try to fetch minimal data to verify connection - just node_info which should always exist
            basic_data = await self._connection.get_data(["node_info"])
            # Verify we got valid data
            return basic_data and "node_info" in basic_data and basic_data["node_info"]
        except Exception as err:
            _LOGGER.warning("Health check failed: %s", err)
            return False
