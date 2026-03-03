"""Data fetching and transformation for Twibi Router API."""

import logging
from typing import Any

from .connection import TwibiConnection
from .enums import NodeRole
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

    async def get_all_data(self, modules: list[str] | None = None) -> dict[str, Any]:
        """Fetch raw router data from the requested modules."""
        if modules is None:
            modules = ["node_info", "online_list", "wan_statistic"]

        return await self.connection.get_data(modules)

    async def get_router_data(self, modules: list[str] | None = None) -> RouterData:
        """Fetch a full typed router snapshot."""
        raw_data = await self.get_all_data(modules)
        return RouterData.from_dict(raw_data, exclude_wired=self.exclude_wired)

    async def get_node_info(self) -> list[NodeInfo]:
        """Fetch and transform node information."""
        raw_data = await self.connection.get_data(["node_info"])
        nodes_data = raw_data.get("node_info", [])

        return [NodeInfo.from_dict(node) for node in nodes_data]

    async def get_online_devices(self) -> list[OnlineDevice]:
        """Fetch and transform online device list."""
        raw_data = await self.connection.get_data(["online_list"])
        devices_data = raw_data.get("online_list", [])

        devices = [OnlineDevice.from_dict(device) for device in devices_data]

        if self.exclude_wired:
            devices = [dev for dev in devices if not dev.is_wired]

        return devices

    async def get_wan_statistics(self) -> list[WanStatistic]:
        """Fetch and transform WAN statistics."""
        raw_data = await self.connection.get_data(["wan_statistic"])
        stats_data = raw_data.get("wan_statistic", [])

        return [WanStatistic.from_dict(stat) for stat in stats_data]

    async def get_available_modules(self) -> list[str]:
        """Get list of available API modules based on api_responses.py."""
        # These are the modules we know are available from the API responses
        return [
            "node_info", "online_list", "wan_statistic", "wan_info", "lan_info",
            "wifi", "guest_info", "static_ip", "port_list", "upnp_info",
            "tr069_info", "remote_web", "dns_conf", "mac_clone", "getversion",
            "net_link_status", "link_module"
        ]

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
        raw_data = await self.connection.get_data(["lan_info"])
        lan_data = raw_data.get("lan_info")
        return LanInfo.from_dict(lan_data) if lan_data else None

    async def get_wan_info(self) -> list[WanInfo]:
        """Fetch and transform WAN connection information."""
        raw_data = await self.connection.get_data(["wan_info"])
        wan_data = raw_data.get("wan_info", [])
        return [WanInfo.from_dict(wan) for wan in wan_data]

    async def get_wifi_info(self) -> WifiInfo | None:
        """Fetch and transform WiFi configuration."""
        raw_data = await self.connection.get_data(["wifi"])
        wifi_data = raw_data.get("wifi")
        return WifiInfo.from_dict(wifi_data) if wifi_data else None

    async def get_guest_info(self) -> GuestInfo | None:
        """Fetch and transform guest network information."""
        raw_data = await self.connection.get_data(["guest_info"])
        guest_data = raw_data.get("guest_info")
        return GuestInfo.from_dict(guest_data) if guest_data else None

    async def get_network_link_status(self) -> list[NetworkLinkStatus]:
        """Fetch and transform network link status."""
        raw_data = await self.connection.get_data(["net_link_status"])
        status_data = raw_data.get("net_link_status", [])
        return [NetworkLinkStatus.from_dict(status) for status in status_data]

    async def get_upnp_info(self) -> UpnpInfo | None:
        """Fetch and transform UPnP configuration."""
        raw_data = await self.connection.get_data(["upnp_info"])
        upnp_data = raw_data.get("upnp_info")
        return UpnpInfo.from_dict(upnp_data) if upnp_data else None
