"""Data fetching and transformation for Twibi Router API."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from ..const import MAIN_SCHEMA
from .const import (
    AVAILABLE_ROUTER_MODULES,
    DEFAULT_ROUTER_DATA_MODULES,
    OPTIONAL_MODULE_REQUEST_DELAY_SECONDS,
    OPTIONAL_ROUTER_DATA_MODULES,
)
from .connection import TwibiConnection
from .enums import NodeRole, RouterModule
from .models import (
    GuestInfo,
    LanInfo,
    NetworkLinkStatus,
    NodeInfo,
    OnlineDevice,
    RouterData,
    UpnpInfo,
    WanInfo,
    WanStatistic,
    WifiInfo,
)

_LOGGER = logging.getLogger(__name__)


class TwibiDataFetcher:
    """Handles data fetching and transformation from Twibi Router."""

    def __init__(self, connection: TwibiConnection, exclude_wired: bool = True) -> None:
        """Initialize the data fetcher."""
        self.connection = connection
        self.exclude_wired = exclude_wired

    async def get_all_data(
        self,
        modules: Sequence[RouterModule] | None = None,
    ) -> dict[str, Any]:
        """Fetch raw router data from the requested modules."""
        requested_modules: Sequence[RouterModule] = (
            DEFAULT_ROUTER_DATA_MODULES if modules is None else modules
        )

        return await self.connection.get_data(requested_modules)

    async def get_router_data(
        self,
        modules: Sequence[RouterModule] | None = None,
    ) -> RouterData:
        """Fetch a full typed router snapshot."""
        raw_data = await self.get_all_data(modules)
        return self._build_router_data(raw_data)

    async def get_router_snapshot(self) -> RouterData:
        """Fetch the default router snapshot with optional modules when available."""
        raw_data = await self.get_all_data(DEFAULT_ROUTER_DATA_MODULES)

        for module in OPTIONAL_ROUTER_DATA_MODULES:
            try:
                raw_data.update(await self.get_all_data([module]))
                await asyncio.sleep(OPTIONAL_MODULE_REQUEST_DELAY_SECONDS)
            except Exception as err:
                _LOGGER.debug("Skipping optional module %s: %s", module, err)

        return self._build_router_data(raw_data)

    async def get_node_info(self) -> list[NodeInfo]:
        """Fetch and transform node information."""
        raw_data = await self.connection.get_data([RouterModule.NODE_INFO])
        nodes_data = raw_data.get(RouterModule.NODE_INFO, [])

        return [NodeInfo.from_dict(node) for node in nodes_data]

    async def get_online_devices(self) -> list[OnlineDevice]:
        """Fetch and transform online device list."""
        raw_data = await self.connection.get_data([RouterModule.ONLINE_LIST])
        devices_data = raw_data.get(RouterModule.ONLINE_LIST, [])

        devices = [OnlineDevice.from_dict(device) for device in devices_data]

        if self.exclude_wired:
            devices = [dev for dev in devices if not dev.is_wired]

        return devices

    async def get_wan_statistics(self) -> list[WanStatistic]:
        """Fetch and transform WAN statistics."""
        raw_data = await self.connection.get_data([RouterModule.WAN_STATISTIC])
        stats_data = raw_data.get(RouterModule.WAN_STATISTIC, [])

        return [WanStatistic.from_dict(stat) for stat in stats_data]

    async def get_available_modules(self) -> list[RouterModule]:
        """Get list of available API modules based on api_responses.py."""
        return list(AVAILABLE_ROUTER_MODULES)

    async def get_device_by_mac(self, mac: str) -> OnlineDevice | None:
        """Get specific device information by MAC address."""
        devices = await self.get_online_devices()
        return next((dev for dev in devices if dev.mac == mac), None)

    async def get_primary_node(self) -> NodeInfo | None:
        """Get the primary router node."""
        nodes = await self.get_node_info()
        return next((node for node in nodes if node.role is NodeRole.PRIMARY), None)

    async def get_secondary_nodes(self) -> list[NodeInfo]:
        """Get all secondary router nodes."""
        nodes = await self.get_node_info()
        return [node for node in nodes if node.role is NodeRole.SECONDARY]

    async def get_lan_info(self) -> LanInfo | None:
        """Fetch and transform LAN configuration."""
        raw_data = await self.connection.get_data([RouterModule.LAN_INFO])
        lan_data = raw_data.get(RouterModule.LAN_INFO)
        return LanInfo.from_dict(lan_data) if lan_data else None

    async def get_wan_info(self) -> list[WanInfo]:
        """Fetch and transform WAN connection information."""
        raw_data = await self.connection.get_data([RouterModule.WAN_INFO])
        wan_data = raw_data.get(RouterModule.WAN_INFO, [])
        return [WanInfo.from_dict(wan) for wan in wan_data]

    async def get_wifi_info(self) -> WifiInfo | None:
        """Fetch and transform WiFi configuration."""
        raw_data = await self.connection.get_data([RouterModule.WIFI])
        wifi_data = raw_data.get(RouterModule.WIFI)
        return WifiInfo.from_dict(wifi_data) if wifi_data else None

    async def get_guest_info(self) -> GuestInfo | None:
        """Fetch and transform guest network information."""
        raw_data = await self.connection.get_data([RouterModule.GUEST_INFO])
        guest_data = raw_data.get(RouterModule.GUEST_INFO)
        return GuestInfo.from_dict(guest_data) if guest_data else None

    async def get_network_link_status(self) -> list[NetworkLinkStatus]:
        """Fetch and transform network link status."""
        raw_data = await self.connection.get_data([RouterModule.NET_LINK_STATUS])
        status_data = raw_data.get(RouterModule.NET_LINK_STATUS, [])
        return [NetworkLinkStatus.from_dict(status) for status in status_data]

    async def get_upnp_info(self) -> UpnpInfo | None:
        """Fetch and transform UPnP configuration."""
        raw_data = await self.connection.get_data([RouterModule.UPNP_INFO])
        upnp_data = raw_data.get(RouterModule.UPNP_INFO)
        return UpnpInfo.from_dict(upnp_data) if upnp_data else None

    def _build_router_data(self, raw_data: dict[str, Any]) -> RouterData:
        """Validate router data and build a typed snapshot."""
        validated_data = MAIN_SCHEMA(raw_data)
        return RouterData.from_dict(
            validated_data,
            exclude_wired=self.exclude_wired,
        )
