"""Data models for Twibi Router API."""

from dataclasses import dataclass, field
from typing import Any, Self

from .enums import (
    AuthenticationErrorCode,
    CommandErrorCode,
    DeviceConnectionType,
    DhcpState,
    DeviceRssiDefault,
    DeviceTxRateDefault,
    FirmwareUpdateState,
    GuestNetworkBandwidthLimit,
    GuestNetworkState,
    GuestNetworkTimeRestriction,
    NetworkLinkState,
    NodeNetworkStatus,
    NodeRole,
    NodeLedState,
    UpnpState,
    WifiMode,
)


@dataclass(frozen=True)
class AuthenticationResult:
    """Represents the outcome of an authentication attempt."""

    authenticated: bool
    errcode: str | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        """Build an authentication result from a router response."""
        errcode = data.get("errcode")
        errcode_str = None if errcode is None else str(errcode)
        return cls(
            authenticated=errcode_str != AuthenticationErrorCode.INVALID_CREDENTIALS,
            errcode=errcode_str,
            raw=data,
        )


@dataclass(frozen=True)
class CommandResult:
    """Represents the outcome of a command sent to the router."""

    command: str
    success: bool
    errcode: str | None = None
    detail: str | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_response(cls, command: str, data: dict[str, Any]) -> Self:
        """Build a command result from a router response."""
        errcode = data.get("errcode")
        errcode_str = None if errcode is None else str(errcode)
        return cls(
            command=command,
            success=errcode_str in (None, CommandErrorCode.SUCCESS),
            errcode=errcode_str,
            raw=data,
        )

    @classmethod
    def from_error(cls, command: str, detail: str) -> Self:
        """Build a failed command result from a local error."""
        return cls(command=command, success=False, detail=detail)

    @property
    def rejected_by_router(self) -> bool:
        """Return True when the router explicitly rejected the command."""
        return not self.success and self.errcode not in (None, CommandErrorCode.SUCCESS)

    @property
    def failed_locally(self) -> bool:
        """Return True when the failure happened before a valid router reply."""
        return not self.success and self.errcode is None


@dataclass
class NodeInfo:
    """Represents a Twibi router node."""

    id: str
    ip: str
    role: NodeRole
    serial_number: str
    led: NodeLedState
    location: str
    lan_mac: str
    wan_mac: str
    wifi_5g_mac: str
    wifi_2g_mac: str
    device_name: str
    device_version: str
    serial: str
    group_serial: str
    uptime: str
    update_date: str
    ipv6: str
    net_status: NodeNetworkStatus
    link_status: str
    link_quality: str | None = None
    netmask: str = ""
    gateway: str = ""
    first_dns: str = ""
    second_dns: str = ""
    up_speed: str = ""
    down_speed: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create NodeInfo from API response dictionary."""
        role = NodeRole(data["role"])
        link_quality = data.get("link_quality") if role is NodeRole.SECONDARY else None

        return cls(
            id=data["id"],
            ip=data["ip"],
            role=role,
            serial_number=data["serial_number"],
            led=NodeLedState(data["led"]),
            location=data["location"],
            lan_mac=data["lan_mac"],
            wan_mac=data["wan_mac"],
            wifi_5g_mac=data["5Gwifi_mac"],
            wifi_2g_mac=data["2Gwifi_mac"],
            device_name=data["dut_name"],
            device_version=data["dut_version"],
            serial=data["sn"],
            group_serial=data["groupsn"],
            uptime=data["Uptime"],
            update_date=data["up_date"],
            ipv6=data["ipv6"],
            net_status=NodeNetworkStatus(data["net_status"]),
            link_status=data["link_status"],
            link_quality=link_quality,
            netmask=data["netmask"],
            gateway=data["gw"],
            first_dns=data["first_dns"],
            second_dns=data["sec_dns"],
            up_speed=data["up_speed"],
            down_speed=data["down_speed"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert NodeInfo back to dictionary format for API compatibility."""
        return {
            "id": self.id,
            "ip": self.ip,
            "role": self.role,
            "netmask": self.netmask,
            "gw": self.gateway,
            "first_dns": self.first_dns,
            "sec_dns": self.second_dns,
            "up_speed": self.up_speed,
            "down_speed": self.down_speed,
            "serial_number": self.serial_number,
            "led": self.led,
            "location": self.location,
            "lan_mac": self.lan_mac,
            "wan_mac": self.wan_mac,
            "5Gwifi_mac": self.wifi_5g_mac,
            "2Gwifi_mac": self.wifi_2g_mac,
            "dut_name": self.device_name,
            "dut_version": self.device_version,
            "sn": self.serial,
            "groupsn": self.group_serial,
            "Uptime": self.uptime,
            "up_date": self.update_date,
            "ipv6": self.ipv6,
            "net_status": self.net_status,
            "link_status": self.link_status,
            "link_quality": self.link_quality,
        }

    @property
    def is_primary(self) -> bool:
        """Check if this is the primary router node."""
        return self.role is NodeRole.PRIMARY

    @property
    def is_led_on(self) -> bool:
        """Check if the LED is currently on."""
        return self.led is NodeLedState.ON


@dataclass
class OnlineDevice:
    """Represents an online device connected to the router."""

    ip: str
    name: str
    mac: str
    download_speed: str
    upload_speed: str
    connect_time: str
    serial: str
    link_type: str | None = None
    rssi: str = DeviceRssiDefault.UNKNOWN
    tx_rate: str = DeviceTxRateDefault.UNKNOWN
    wifi_mode: WifiMode = WifiMode.WIRED

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create OnlineDevice from API response dictionary."""
        wifi_mode = WifiMode(data["wifi_mode"])

        return cls(
            ip=data["dev_ip"],
            name=data["dev_name"],
            mac=data["dev_mac"],
            download_speed=data["download_speed"],
            upload_speed=data["upload_speed"],
            connect_time=data["connect_time"],
            serial=data["sn"],
            link_type=data.get("link_type"),
            rssi=data["rssi"],
            tx_rate=data["tx_rate"],
            wifi_mode=wifi_mode,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert OnlineDevice back to dictionary format for API compatibility."""
        return {
            "dev_ip": self.ip,
            "dev_name": self.name,
            "dev_mac": self.mac,
            "download_speed": self.download_speed,
            "upload_speed": self.upload_speed,
            "connect_time": self.connect_time,
            "sn": self.serial,
            "link_type": self.link_type,
            "rssi": self.rssi,
            "tx_rate": self.tx_rate,
            "wifi_mode": self.wifi_mode,
        }

    @property
    def is_wired(self) -> bool:
        """Check if device is connected via Ethernet."""
        return self.wifi_mode is WifiMode.WIRED

    @property
    def connection_type(self) -> DeviceConnectionType:
        """Get human-readable connection type."""
        return self.wifi_mode.connection_type

    @property
    def display_name(self) -> str:
        """Get display name for the device."""
        return self.name or f"Device {self.mac}"


@dataclass
class WanStatistic:
    """Represents WAN statistics from the router."""

    id: str
    up_speed: str
    down_speed: str
    total_upload: str
    total_download: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create WanStatistic from API response dictionary."""
        return cls(
            id=data["id"],
            up_speed=data["up_speed"],
            down_speed=data["down_speed"],
            total_upload=data["ttotal_up"],
            total_download=data["ttotal_down"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert WanStatistic back to dictionary format for API compatibility."""
        return {
            "id": self.id,
            "up_speed": self.up_speed,
            "down_speed": self.down_speed,
            "ttotal_up": self.total_upload,
            "ttotal_down": self.total_download,
        }

    @property
    def up_speed_float(self) -> float:
        """Get upload speed as float value."""
        try:
            return float(self.up_speed)
        except (ValueError, TypeError):
            return 0.0

    @property
    def down_speed_float(self) -> float:
        """Get download speed as float value."""
        try:
            return float(self.down_speed)
        except (ValueError, TypeError):
            return 0.0


@dataclass
class WifiInfo:
    """Represents WiFi configuration information."""

    ssid: str
    security_type: str
    security_mode: str
    password: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create WifiInfo from API response dictionary."""
        return cls(
            ssid=data["ssid"],
            security_type=data["type"],
            security_mode=data["security"],
            password=data["pass"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert WifiInfo back to dictionary format for API compatibility."""
        return {
            "ssid": self.ssid,
            "type": self.security_type,
            "security": self.security_mode,
            "pass": self.password,
        }


@dataclass
class GuestInfo:
    """Represents guest network information."""

    enabled: bool
    ssid: str
    password: str
    time_restriction: GuestNetworkTimeRestriction
    bandwidth_limit: GuestNetworkBandwidthLimit

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create GuestInfo from API response dictionary."""
        return cls(
            enabled=data["guest_en"] == GuestNetworkState.ENABLED,
            ssid=data["guest_ssid"],
            password=data["guest_pass"],
            time_restriction=GuestNetworkTimeRestriction(data["guest_time"]),
            bandwidth_limit=GuestNetworkBandwidthLimit(data["limit"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert GuestInfo back to dictionary format for API compatibility."""
        return {
            "guest_en": (
                GuestNetworkState.ENABLED
                if self.enabled
                else GuestNetworkState.DISABLED
            ),
            "guest_ssid": self.ssid,
            "guest_pass": self.password,
            "guest_time": self.time_restriction,
            "limit": self.bandwidth_limit,
        }


@dataclass
class LanInfo:
    """Represents LAN configuration information."""

    lan_ip: str
    lan_mask: str
    dhcp_enabled: bool
    start_ip: str
    end_ip: str
    lease_time: str
    dns1: str
    dns2: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create LanInfo from API response dictionary."""
        return cls(
            lan_ip=data["lan_ip"],
            lan_mask=data["lan_mask"],
            dhcp_enabled=data["dhcp_en"] == DhcpState.ENABLED,
            start_ip=data["start_ip"],
            end_ip=data["end_ip"],
            lease_time=data["lease_time"],
            dns1=data["dns1"],
            dns2=data["dns2"],
        )


@dataclass
class WanInfo:
    """Represents WAN connection information."""

    id: str
    ip: str
    netmask: str
    gateway: str
    mac: str
    first_dns: str
    second_dns: str
    ipv6: str
    ipv6_gateway: str
    ipv6_first_dns: str
    ipv6_second_dns: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create WanInfo from API response dictionary."""
        return cls(
            id=data["id"],
            ip=data["ip"],
            netmask=data["netmask"],
            gateway=data["gw"],
            mac=data["mac"],
            first_dns=data["first_dns"],
            second_dns=data["sec_dns"],
            ipv6=data["ipv6"],
            ipv6_gateway=data["ipv6_gw"],
            ipv6_first_dns=data["ipv6_first_dns"],
            ipv6_second_dns=data["ipv6_sec_dns"],
        )


@dataclass
class VersionInfo:
    """Represents firmware version information."""

    has_new: bool
    version: str
    changelog: str
    current_version: str
    system_has_new: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create VersionInfo from API response dictionary."""
        return cls(
            has_new=data["hasNew"] == FirmwareUpdateState.UPDATE_AVAILABLE,
            version=data["version"],
            changelog=data["changelog"],
            current_version=data["current_version"],
            system_has_new=(data["sysHasNew"] == FirmwareUpdateState.UPDATE_AVAILABLE),
        )


@dataclass
class NetworkLinkStatus:
    """Represents network link status."""

    net_status: NetworkLinkState
    id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create NetworkLinkStatus from API response dictionary."""
        return cls(
            net_status=NetworkLinkState(data["net_status"]),
            id=data["id"],
        )

    @property
    def is_connected(self) -> bool:
        """Check if network is connected."""
        return self.net_status == NetworkLinkState.CONNECTED


@dataclass
class UpnpInfo:
    """Represents UPnP configuration."""

    upnp_enabled: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create UpnpInfo from API response dictionary."""
        return cls(
            upnp_enabled=data["upnp_en"] == UpnpState.ENABLED,
        )


@dataclass
class RouterData:
    """Represents the full typed data snapshot used by the integration."""

    node_info: list[NodeInfo]
    online_list: list[OnlineDevice]
    wan_statistic: list[WanStatistic]
    wan_info: list[WanInfo] = field(default_factory=list)
    lan_info: LanInfo | None = None
    wifi: WifiInfo | None = None
    guest_info: GuestInfo | None = None
    getversion: VersionInfo | None = None
    upnp_info: UpnpInfo | None = None
    net_link_status: list[NetworkLinkStatus] = field(default_factory=list)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        exclude_wired: bool = False,
    ) -> Self:
        """Build a typed router snapshot from a validated API payload."""
        online_list = [OnlineDevice.from_dict(device) for device in data["online_list"]]
        if exclude_wired:
            online_list = [device for device in online_list if not device.is_wired]

        wan_info_data = data.get("wan_info") or []
        net_link_status_data = data.get("net_link_status") or []

        lan_info_data = data.get("lan_info")
        wifi_data = data.get("wifi")
        guest_info_data = data.get("guest_info")
        version_data = data.get("getversion")
        upnp_info_data = data.get("upnp_info")

        return cls(
            node_info=[NodeInfo.from_dict(node) for node in data["node_info"]],
            online_list=online_list,
            wan_statistic=[
                WanStatistic.from_dict(statistic)
                for statistic in data["wan_statistic"]
            ],
            wan_info=[WanInfo.from_dict(wan) for wan in wan_info_data],
            lan_info=LanInfo.from_dict(lan_info_data) if lan_info_data else None,
            wifi=WifiInfo.from_dict(wifi_data) if wifi_data else None,
            guest_info=GuestInfo.from_dict(guest_info_data) if guest_info_data else None,
            getversion=VersionInfo.from_dict(version_data) if version_data else None,
            upnp_info=UpnpInfo.from_dict(upnp_info_data) if upnp_info_data else None,
            net_link_status=[
                NetworkLinkStatus.from_dict(status)
                for status in net_link_status_data
            ],
        )

    @property
    def primary_node(self) -> NodeInfo | None:
        """Return the primary node from the current snapshot."""
        return next(
            (node for node in self.node_info if node.role is NodeRole.PRIMARY),
            None,
        )

    @property
    def secondary_nodes(self) -> list[NodeInfo]:
        """Return all secondary nodes from the current snapshot."""
        return [
            node
            for node in self.node_info
            if node.role is NodeRole.SECONDARY
        ]

    def get_node_by_serial(self, serial: str) -> NodeInfo | None:
        """Return a node by serial number."""
        return next((node for node in self.node_info if node.serial == serial), None)

    def get_node_by_id(self, node_id: str) -> NodeInfo | None:
        """Return a node by node ID."""
        return next((node for node in self.node_info if node.id == node_id), None)

    def get_device_by_mac(self, mac: str) -> OnlineDevice | None:
        """Return a client device by MAC address."""
        return next((device for device in self.online_list if device.mac == mac), None)

    def get_wan_statistic(self, statistic_id: str) -> WanStatistic | None:
        """Return a WAN statistic entry by ID."""
        return next(
            (
                statistic
                for statistic in self.wan_statistic
                if statistic.id == statistic_id
            ),
            None,
        )
