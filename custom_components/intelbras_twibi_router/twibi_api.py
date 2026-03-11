"""Improved API module for interacting with Twibi Router."""

import logging
from collections.abc import Sequence
from typing import Any

import aiohttp

from .api import (
    APIError,
    AuthenticationError,
    TwibiConnection,
    TwibiController,
    TwibiDataFetcher,
)
from .api.const import DEFAULT_TIMEOUT
from .api.enums import (
    GuestNetworkBandwidthLimit,
    GuestNetworkTimeRestriction,
    RouterModule,
    WifiSecurityMode,
    WifiSecurityType,
)
from .api.models import (
    AuthenticationResult,
    CommandResult,
    NodeInfo,
    OnlineDevice,
    RouterData,
    WanStatistic,
)

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
        self._exclude_wired = exclude_wired
        self.update_interval = update_interval

        # Initialize the new API components
        self._connection = TwibiConnection(host, password, session, timeout)
        self._data_fetcher = TwibiDataFetcher(self._connection, self._exclude_wired)
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
    def exclude_wired(self) -> bool:
        """Return whether wired devices are excluded."""
        return self._exclude_wired

    @exclude_wired.setter
    def exclude_wired(self, value: bool) -> None:
        """Update the wired-device filter in both API and fetcher state."""
        self._exclude_wired = value
        self._data_fetcher.exclude_wired = value

    @property
    def controller(self) -> TwibiController:
        """Get the controller."""
        return self._controller

    async def authenticate(self) -> AuthenticationResult:
        """Authenticate with the router and return a typed result."""
        return await self._connection.authenticate()

    async def get_data(self, module_list: Sequence[RouterModule]) -> dict[str, Any]:
        """Retrieve raw module data from the router."""
        return await self._data_fetcher.get_all_data(module_list)

    async def get_router_data(
        self,
        modules: Sequence[RouterModule] | None = None,
    ) -> RouterData:
        """Retrieve a typed router snapshot."""
        return await self._data_fetcher.get_router_data(modules)

    async def get_router_snapshot(self) -> RouterData:
        """Retrieve the default typed router snapshot used by the coordinator."""
        return await self._data_fetcher.get_router_snapshot()

    async def get_node_info(self) -> list[NodeInfo]:
        """Get node information."""
        return await self._data_fetcher.get_node_info()

    async def get_online_devices(self) -> list[OnlineDevice]:
        """Get online devices."""
        return await self._data_fetcher.get_online_devices()

    async def get_wan_statistics(self) -> list[WanStatistic]:
        """Get WAN statistics."""
        return await self._data_fetcher.get_wan_statistics()

    async def set_led_status(self, serial: str, enabled: bool) -> bool:
        """Set LED status for a node."""
        return await self._controller.set_led_status(serial, enabled)

    async def set_led_status_result(self, serial: str, enabled: bool) -> CommandResult:
        """Set LED status for a node and return a typed result."""
        return await self._controller.set_led_status_result(serial, enabled)

    async def restart_router(self) -> bool:
        """Restart the router."""
        return await self._controller.restart_router()

    async def restart_router_result(self) -> CommandResult:
        """Restart the router and return a typed result."""
        return await self._controller.restart_router_result()

    async def set_wifi_config(
        self,
        ssid: str,
        password: str,
        security_type: WifiSecurityType = WifiSecurityType.AES,
        security_mode: WifiSecurityMode = WifiSecurityMode.PSK_PSK2,
    ) -> bool:
        """Set WiFi configuration."""
        return await self._controller.set_wifi_config(
            ssid, password, security_type, security_mode
        )

    async def set_wifi_config_result(
        self,
        ssid: str,
        password: str,
        security_type: WifiSecurityType = WifiSecurityType.AES,
        security_mode: WifiSecurityMode = WifiSecurityMode.PSK_PSK2,
    ) -> CommandResult:
        """Set WiFi configuration and return a typed result."""
        return await self._controller.set_wifi_config_result(
            ssid,
            password,
            security_type,
            security_mode,
        )

    async def set_guest_network(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: GuestNetworkTimeRestriction = GuestNetworkTimeRestriction.ALWAYS,
        bandwidth_limit: GuestNetworkBandwidthLimit = GuestNetworkBandwidthLimit.UNLIMITED,
    ) -> bool:
        """Configure guest network."""
        return await self._controller.set_guest_network(
            enabled, ssid, password, time_restriction, bandwidth_limit
        )

    async def set_guest_network_result(
        self,
        enabled: bool,
        ssid: str | None = None,
        password: str | None = None,
        time_restriction: GuestNetworkTimeRestriction = GuestNetworkTimeRestriction.ALWAYS,
        bandwidth_limit: GuestNetworkBandwidthLimit = GuestNetworkBandwidthLimit.UNLIMITED,
    ) -> CommandResult:
        """Configure guest network and return a typed result."""
        return await self._controller.set_guest_network_result(
            enabled,
            ssid,
            password,
            time_restriction,
            bandwidth_limit,
        )

    async def set_upnp(self, enabled: bool) -> bool:
        """Enable or disable UPnP."""
        return await self._controller.set_upnp_status(enabled)

    async def set_upnp_result(self, enabled: bool) -> CommandResult:
        """Enable or disable UPnP and return a typed result."""
        return await self._controller.set_upnp_status_result(enabled)

    async def get_device_by_mac(self, mac: str) -> OnlineDevice | None:
        """Get specific device by MAC address."""
        return await self._data_fetcher.get_device_by_mac(mac)

    async def get_primary_node(self) -> NodeInfo | None:
        """Get the primary router node."""
        return await self._data_fetcher.get_primary_node()

    async def get_secondary_nodes(self) -> list[NodeInfo]:
        """Get all secondary router nodes."""
        return await self._data_fetcher.get_secondary_nodes()

    def invalidate_auth(self) -> None:
        """Invalidate current authentication state."""
        self._connection.invalidate_auth()

    async def health_check(self) -> bool:
        """Perform a health check on the API connection."""
        try:
            basic_data = await self._data_fetcher.get_all_data([RouterModule.NODE_INFO])
        except AuthenticationError as err:
            _LOGGER.debug("Health check failed: %s", err)
            if str(err) == "Invalid credentials":
                raise
            return False
        except APIError as err:
            _LOGGER.debug("Health check failed: %s", err)
            return False

        return bool(basic_data.get(RouterModule.NODE_INFO))
