"""Sensor platform for Twibi Router integration."""

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator_v2 import TwibiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router sensor entities."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: TwibiCoordinator = entry_data["coordinator"]
    host = entry_data["host"]

    entities = []

    # WAN Statistics sensors
    if coordinator.data.get("wan_statistic"):
        for wan_stat in coordinator.data["wan_statistic"]:
            wan_id = wan_stat.get("id", "1")
            entities.extend([
                TwibiWanUploadSpeedSensor(coordinator, host, wan_id),
                TwibiWanDownloadSpeedSensor(coordinator, host, wan_id),
            ])

    # Router information sensors - assign to correct device
    if coordinator.data.get("node_info"):
        for node in coordinator.data["node_info"]:
            node_id = node.get("id", "0")
            node_serial = node.get("sn", "")
            serial_suffix = node_serial[-4:] if node_serial else node_id
            is_primary = node.get("role") == "1"
            # Use host for primary router (role=1), serial for secondary routers (role=0)
            device_identifier = host if is_primary else node_serial

            entities.extend([
                TwibiRouterUptimeSensor(coordinator, device_identifier, node_id, is_primary, serial_suffix, node_serial),
                TwibiRouterSerialSensor(coordinator, device_identifier, node_id, is_primary, serial_suffix, node_serial),
            ])

            # Only add link quality sensor for secondary routers (primary is ethernet connected)
            if not is_primary:
                entities.append(
                    TwibiRouterLinkQualitySensor(coordinator, device_identifier, node_id, is_primary, serial_suffix, node_serial)
                )

    # Network information sensors
    entities.extend([
        TwibiConnectedDevicesSensor(coordinator, host),
        TwibiNetworkStatusSensor(coordinator, host),
    ])

    # LAN information sensor
    if coordinator.data.get("lan_info"):
        entities.append(TwibiLanInfoSensor(coordinator, host))

    # WAN information sensor
    if coordinator.data.get("wan_info"):
        entities.append(TwibiWanInfoSensor(coordinator, host))

    # WiFi QR Code sensors
    if coordinator.data.get("wifi"):
        entities.append(TwibiWifiQRCodeSensor(coordinator, host))

    if coordinator.data.get("guest_info"):
        entities.append(TwibiGuestWifiQRCodeSensor(coordinator, host))

    async_add_entities(entities)


class TwibiBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Twibi Router sensors."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        host: str,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._host = host
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = f"{host}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"Twibi Router {host}",
            "manufacturer": "Intelbras",
            "model": "Twibi Router",
        }


class TwibiWanUploadSpeedSensor(TwibiBaseSensor):
    """WAN upload speed sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str, wan_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, f"wan_upload_speed_{wan_id}", "WAN Upload Speed")
        self._wan_id = wan_id
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND

    @property
    def native_value(self) -> float | None:
        """Return the upload speed."""
        wan_stats = self.coordinator.data.get("wan_statistic", [])
        for stat in wan_stats:
            if stat.get("id") == self._wan_id:
                try:
                    return float(stat.get("up_speed", 0))
                except (ValueError, TypeError):
                    return 0.0
        return None


class TwibiWanDownloadSpeedSensor(TwibiBaseSensor):
    """WAN download speed sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str, wan_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, f"wan_download_speed_{wan_id}", "WAN Download Speed")
        self._wan_id = wan_id
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND

    @property
    def native_value(self) -> float | None:
        """Return the download speed."""
        wan_stats = self.coordinator.data.get("wan_statistic", [])
        for stat in wan_stats:
            if stat.get("id") == self._wan_id:
                try:
                    return float(stat.get("down_speed", 0))
                except (ValueError, TypeError):
                    return 0.0
        return None


class TwibiRouterUptimeSensor(TwibiBaseSensor):
    """Router uptime sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_uptime_{full_serial[-4:]}", "Uptime")
        self._node_id = node_id
        self._is_primary = is_primary
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        # Set entity_id to match LED pattern exactly
        self.entity_id = f"sensor.uptime_{full_serial[-4:]}"

        # Store previous values to detect real changes
        self._last_uptime_seconds = None
        self._attr_should_poll = False  # We rely on coordinator updates

        # Override device info for proper assignment
        if not is_primary:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (DOMAIN, coordinator.hass.data[DOMAIN][coordinator.config_entry.entry_id]["host"]),
            }

    def _uptime_value_changed(self, old_value: datetime | None, new_value: datetime | None) -> bool:
        """Check if uptime value has changed significantly (like UniFi integration)."""
        if old_value is None or new_value is None:
            return old_value != new_value

        if isinstance(old_value, datetime) and isinstance(new_value, datetime):
            # Only update if the difference is more than 120 seconds (like UniFi)
            return new_value != old_value and abs((new_value - old_value).total_seconds()) > 120

        return old_value != new_value

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Get current uptime
        nodes = self.coordinator.data.get("node_info", [])
        current_uptime = None

        for node in nodes:
            if node.get("id") == self._node_id:
                try:
                    current_uptime = int(node.get("Uptime", 0))
                    break
                except (ValueError, TypeError):
                    pass

        if current_uptime is not None and current_uptime > 0:
            # Calculate new startup time
            new_startup_time = dt_util.now() - timedelta(seconds=current_uptime)

            # Only update if the value has changed significantly
            if self._uptime_value_changed(self._attr_native_value, new_startup_time):
                self._last_uptime_seconds = current_uptime
                self._attr_native_value = new_startup_time
                # Only call parent update if value actually changed significantly
                super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the startup timestamp."""
        return self._attr_native_value

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._attr_native_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        nodes = self.coordinator.data.get("node_info", [])
        for node in nodes:
            if node.get("id") == self._node_id:
                return {
                    "device_name": node.get("dut_name", ""),
                    "serial_number": node.get("sn", ""),
                    "last_update": node.get("up_date", ""),
                }
        return {}


class TwibiRouterSerialSensor(TwibiBaseSensor):
    """Router serial number sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_serial_{full_serial[-4:]}", "Serial Number")
        self._node_id = node_id
        self._is_primary = is_primary
        # Set entity_id to match LED pattern exactly
        self.entity_id = f"sensor.serial_number_{full_serial[-4:]}"

        # Override device info for proper assignment
        if not is_primary:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (DOMAIN, coordinator.hass.data[DOMAIN][coordinator.config_entry.entry_id]["host"]),
            }

    @property
    def native_value(self) -> str | None:
        """Return the router serial number."""
        nodes = self.coordinator.data.get("node_info", [])
        for node in nodes:
            if node.get("id") == self._node_id:
                return node.get("sn", "")
        return None


class TwibiRouterLinkQualitySensor(TwibiBaseSensor):
    """Router link quality sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_link_quality_{full_serial[-4:]}", "Link Quality")
        self._node_id = node_id
        self._is_primary = is_primary
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        # Set entity_id to match LED pattern exactly
        self.entity_id = f"sensor.link_quality_{full_serial[-4:]}"

        # Override device info for proper assignment
        if not is_primary:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (DOMAIN, coordinator.hass.data[DOMAIN][coordinator.config_entry.entry_id]["host"]),
            }

    @property
    def native_value(self) -> int | None:
        """Return the link quality."""
        nodes = self.coordinator.data.get("node_info", [])
        for node in nodes:
            if node.get("id") == self._node_id:
                link_quality = node.get("link_quality")
                if link_quality is not None:
                    try:
                        return int(link_quality)
                    except (ValueError, TypeError):
                        return None
        return None


class TwibiConnectedDevicesSensor(TwibiBaseSensor):
    """Connected devices count sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "connected_devices", "Connected Devices")
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the number of connected devices."""
        return len(self.coordinator.data.get("online_list", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        devices = self.coordinator.data.get("online_list", [])
        device_list = [{
            "name": device.get("dev_name", "Unknown"),
            "mac": device.get("dev_mac", ""),
            "ip": device.get("dev_ip", ""),
            "connection": device.get("wifi_mode", "--"),
        } for device in devices]
        return {"devices": device_list}


class TwibiNetworkStatusSensor(TwibiBaseSensor):
    """Network status sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "network_status", "Network Status")

    @property
    def native_value(self) -> str:
        """Return the network status."""
        nodes = self.coordinator.data.get("node_info", [])
        primary_node = next((node for node in nodes if node.get("role") == "1"), None)
        if primary_node:
            net_status = primary_node.get("net_status", "0")
            return "Connected" if net_status == "1" else "Disconnected"
        return "Unknown"


class TwibiLanInfoSensor(TwibiBaseSensor):
    """LAN information sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "lan_info", "LAN Information")

    @property
    def native_value(self) -> str:
        """Return the LAN IP address."""
        lan_info = self.coordinator.data.get("lan_info", {})
        return lan_info.get("lan_ip", "")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        lan_info = self.coordinator.data.get("lan_info", {})
        return {
            "subnet_mask": lan_info.get("lan_mask", ""),
            "dhcp_enabled": lan_info.get("dhcp_en", "0") == "1",
            "dhcp_start": lan_info.get("start_ip", ""),
            "dhcp_end": lan_info.get("end_ip", ""),
            "lease_time": lan_info.get("lease_time", ""),
            "dns1": lan_info.get("dns1", ""),
            "dns2": lan_info.get("dns2", ""),
        }


class TwibiWanInfoSensor(TwibiBaseSensor):
    """WAN information sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "wan_info", "WAN Information")

    @property
    def native_value(self) -> str:
        """Return the WAN IP address."""
        wan_info = self.coordinator.data.get("wan_info", [])
        if wan_info:
            return wan_info[0].get("ip", "")
        return ""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        wan_info = self.coordinator.data.get("wan_info", [])
        if wan_info:
            info = wan_info[0]
            return {
                "netmask": info.get("netmask", ""),
                "gateway": info.get("gw", ""),
                "mac": info.get("mac", ""),
                "dns1": info.get("first_dns", ""),
                "dns2": info.get("sec_dns", ""),
                "ipv6": info.get("ipv6", ""),
            }
        return {}


class TwibiWifiQRCodeSensor(TwibiBaseSensor):
    """WiFi QR Code sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "wifi_qr_code", "WiFi QR Code")
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return the WiFi QR code string."""
        wifi_info = self.coordinator.data.get("wifi", {})
        ssid = wifi_info.get("ssid", "")
        password = wifi_info.get("pass", "")
        security = wifi_info.get("security", "")

        if not ssid:
            return ""

        # Determine security type for QR code
        if "psk" in security.lower():
            auth_type = "WPA"
        elif security.lower() == "none":
            auth_type = "nopass"
        else:
            auth_type = "WPA"

        # Generate WiFi QR code string in standard format
        if auth_type == "nopass":
            qr_string = f"WIFI:T:nopass;S:{ssid};;"
        else:
            qr_string = f"WIFI:T:{auth_type};S:{ssid};P:{password};;"

        return qr_string

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        wifi_info = self.coordinator.data.get("wifi", {})
        return {
            "ssid": wifi_info.get("ssid", ""),
            "security": wifi_info.get("security", ""),
            "type": wifi_info.get("type", ""),
            "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
        }


class TwibiGuestWifiQRCodeSensor(TwibiBaseSensor):
    """Guest WiFi QR Code sensor."""

    def __init__(self, coordinator: TwibiCoordinator, host: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, host, "guest_wifi_qr_code", "Guest WiFi QR Code")
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return the Guest WiFi QR code string."""
        guest_info = self.coordinator.data.get("guest_info", {})
        ssid = guest_info.get("guest_ssid", "")
        password = guest_info.get("guest_pass", "")
        enabled = guest_info.get("guest_en", "0") == "1"

        if not ssid or not enabled:
            return ""

        # Generate Guest WiFi QR code string
        if password:
            qr_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"
        else:
            qr_string = f"WIFI:T:nopass;S:{ssid};;"

        return qr_string

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        guest_info = self.coordinator.data.get("guest_info", {})
        return {
            "ssid": guest_info.get("guest_ssid", ""),
            "enabled": guest_info.get("guest_en", "0") == "1",
            "time_limit": guest_info.get("guest_time", ""),
            "bandwidth_limit": guest_info.get("limit", ""),
            "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
        }
