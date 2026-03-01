"""Data models for Twibi Router API."""

from dataclasses import dataclass
from typing import Any


@dataclass
class NodeInfo:
    """Represents a Twibi router node."""

    id: str
    ip: str
    role: str  # "0" for secondary, "1" for primary
    serial_number: str
    led: str  # "0" for off, "1" for on
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
    net_status: str
    link_status: str
    link_quality: str | None = None
    netmask: str = ""
    gateway: str = ""
    first_dns: str = ""
    second_dns: str = ""
    up_speed: str = ""
    down_speed: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NodeInfo":
        """Create NodeInfo from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            ip=data.get("ip", ""),
            role=data.get("role", "0"),
            serial_number=data.get("serial_number", ""),
            led=data.get("led", "0"),
            location=data.get("location", ""),
            lan_mac=data.get("lan_mac", ""),
            wan_mac=data.get("wan_mac", ""),
            wifi_5g_mac=data.get("5Gwifi_mac", ""),
            wifi_2g_mac=data.get("2Gwifi_mac", ""),
            device_name=data.get("dut_name", ""),
            device_version=data.get("dut_version", ""),
            serial=data.get("sn", ""),
            group_serial=data.get("groupsn", ""),
            uptime=data.get("Uptime", ""),
            update_date=data.get("up_date", ""),
            ipv6=data.get("ipv6", ""),
            net_status=data.get("net_status", ""),
            link_status=data.get("link_status", ""),
            link_quality=str(data.get("link_quality")) if data.get("link_quality") is not None else None,
            netmask=data.get("netmask", ""),
            gateway=data.get("gw", ""),
            first_dns=data.get("first_dns", ""),
            second_dns=data.get("sec_dns", ""),
            up_speed=data.get("up_speed", ""),
            down_speed=data.get("down_speed", ""),
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
        return self.role == "1"

    @property
    def is_led_on(self) -> bool:
        """Check if the LED is currently on."""
        return self.led == "1"


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
    rssi: str = "0"
    tx_rate: str = "0"
    wifi_mode: str = "--"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OnlineDevice":
        """Create OnlineDevice from API response dictionary."""
        return cls(
            ip=data.get("dev_ip", ""),
            name=data.get("dev_name", ""),
            mac=data.get("dev_mac", ""),
            download_speed=data.get("download_speed", "0"),
            upload_speed=data.get("upload_speed", "0"),
            connect_time=data.get("connect_time", ""),
            serial=data.get("sn", ""),
            link_type=data.get("link_type"),
            rssi=data.get("rssi", "0"),
            tx_rate=data.get("tx_rate", "0"),
            wifi_mode=data.get("wifi_mode", "--"),
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
        return self.wifi_mode == "--"

    @property
    def connection_type(self) -> str:
        """Get human-readable connection type."""
        if self.is_wired:
            return "Ethernet"
        match self.wifi_mode:
            case "AC":
                return "5GHz"
            case "BGN":
                return "2.4GHz"
        return "Unknown"

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
    def from_dict(cls, data: dict[str, Any]) -> "WanStatistic":
        """Create WanStatistic from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            up_speed=data.get("up_speed", "0"),
            down_speed=data.get("down_speed", "0"),
            total_upload=data.get("ttotal_up", "0"),
            total_download=data.get("ttotal_down", "0"),
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
    def from_dict(cls, data: dict[str, Any]) -> "WifiInfo":
        """Create WifiInfo from API response dictionary."""
        return cls(
            ssid=data.get("ssid", ""),
            security_type=data.get("type", ""),
            security_mode=data.get("security", ""),
            password=data.get("pass", ""),
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
    time_restriction: str
    bandwidth_limit: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GuestInfo":
        """Create GuestInfo from API response dictionary."""
        return cls(
            enabled=data.get("guest_en", "0") == "1",
            ssid=data.get("guest_ssid", ""),
            password=data.get("guest_pass", ""),
            time_restriction=data.get("guest_time", ""),
            bandwidth_limit=data.get("limit", "0"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert GuestInfo back to dictionary format for API compatibility."""
        return {
            "guest_en": "1" if self.enabled else "0",
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
    def from_dict(cls, data: dict[str, Any]) -> "LanInfo":
        """Create LanInfo from API response dictionary."""
        return cls(
            lan_ip=data.get("lan_ip", ""),
            lan_mask=data.get("lan_mask", ""),
            dhcp_enabled=data.get("dhcp_en", "0") == "1",
            start_ip=data.get("start_ip", ""),
            end_ip=data.get("end_ip", ""),
            lease_time=data.get("lease_time", ""),
            dns1=data.get("dns1", ""),
            dns2=data.get("dns2", ""),
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
    def from_dict(cls, data: dict[str, Any]) -> "WanInfo":
        """Create WanInfo from API response dictionary."""
        return cls(
            id=data.get("id", ""),
            ip=data.get("ip", ""),
            netmask=data.get("netmask", ""),
            gateway=data.get("gw", ""),
            mac=data.get("mac", ""),
            first_dns=data.get("first_dns", ""),
            second_dns=data.get("sec_dns", ""),
            ipv6=data.get("ipv6", ""),
            ipv6_gateway=data.get("ipv6_gw", ""),
            ipv6_first_dns=data.get("ipv6_first_dns", ""),
            ipv6_second_dns=data.get("ipv6_sec_dns", ""),
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
    def from_dict(cls, data: dict[str, Any]) -> "VersionInfo":
        """Create VersionInfo from API response dictionary."""
        return cls(
            has_new=data.get("hasNew", "0") == "1",
            version=data.get("version", ""),
            changelog=data.get("changelog", ""),
            current_version=data.get("current_version", ""),
            system_has_new=data.get("sysHasNew", "0") == "1",
        )


@dataclass
class NetworkLinkStatus:
    """Represents network link status."""

    net_status: str
    id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetworkLinkStatus":
        """Create NetworkLinkStatus from API response dictionary."""
        return cls(
            net_status=data.get("net_status", ""),
            id=data.get("id", ""),
        )

    @property
    def is_connected(self) -> bool:
        """Check if network is connected."""
        return self.net_status == "3"


@dataclass
class UpnpInfo:
    """Represents UPnP configuration."""

    upnp_enabled: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpnpInfo":
        """Create UpnpInfo from API response dictionary."""
        return cls(
            upnp_enabled=data.get("upnp_en", "0") == "1",
        )
