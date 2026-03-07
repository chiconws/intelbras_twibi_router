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

from .api.enums import NodeNetworkStatus, NodeRole, RouterConnectionState
from .coordinator import TwibiCoordinator
from .const import DOMAIN
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router sensor entities."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator: TwibiCoordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    entities = []

    # WAN Statistics sensors
    if coordinator.data.wan_statistic:
        for wan_stat in coordinator.data.wan_statistic:
            wan_id = wan_stat.id
            entities.extend([
                TwibiWanUploadSpeedSensor(coordinator, primary_device_identifier, wan_id),
                TwibiWanDownloadSpeedSensor(coordinator, primary_device_identifier, wan_id),
            ])

    # Router information sensors - assign to correct device
    if coordinator.data.node_info:
        for node in coordinator.data.node_info:
            node_id = node.id
            node_serial = node.serial
            serial_suffix = node_serial[-4:] if node_serial else node_id
            is_primary = node.role is NodeRole.PRIMARY
            # Use the stable primary identifier for the main router and serial for
            # secondary routers.
            device_identifier = primary_device_identifier if is_primary else node_serial

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
        TwibiConnectedDevicesSensor(coordinator, primary_device_identifier),
        TwibiNetworkStatusSensor(coordinator, primary_device_identifier),
    ])

    # LAN information sensor
    entities.append(TwibiLanInfoSensor(coordinator, primary_device_identifier))

    # WAN information sensor
    entities.append(TwibiWanInfoSensor(coordinator, primary_device_identifier))

    # WiFi QR Code sensors
    entities.append(TwibiWifiQRCodeSensor(coordinator, primary_device_identifier))

    entities.append(TwibiGuestWifiQRCodeSensor(coordinator, primary_device_identifier))

    async_add_entities(entities)


class TwibiBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Twibi Router sensors."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_identifier = device_identifier
        self._sensor_type = sensor_type
        self._attr_name = name
        self._attr_unique_id = f"{device_identifier}_{sensor_type}"
        self._attr_device_info = {"identifiers": {(DOMAIN, device_identifier)}}


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
        statistic = self.coordinator.data.get_wan_statistic(self._wan_id)
        return statistic.up_speed_float if statistic else None


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
        statistic = self.coordinator.data.get_wan_statistic(self._wan_id)
        return statistic.down_speed_float if statistic else None


class TwibiRouterUptimeSensor(TwibiBaseSensor):
    """Router uptime sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_uptime_{full_serial[-4:]}", "Uptime")
        self._node_id = node_id
        self._is_primary = is_primary
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_value = None
        self._attr_should_poll = False  # We rely on coordinator updates
        self._sync_native_value()

        # Override device info for proper assignment
        if not is_primary:
            runtime_data = get_runtime_data(
                coordinator.hass,
                coordinator.config_entry.entry_id,
            )
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (
                    DOMAIN,
                    runtime_data.primary_device_identifier,
                ),
            }

    def _uptime_value_changed(self, old_value: datetime | None, new_value: datetime | None) -> bool:
        """Check if uptime value has changed significantly (like UniFi integration)."""
        if old_value is None or new_value is None:
            return old_value != new_value

        if isinstance(old_value, datetime) and isinstance(new_value, datetime):
            # Only update if the difference is more than 120 seconds (like UniFi)
            return new_value != old_value and abs((new_value - old_value).total_seconds()) > 120

        return old_value != new_value

    def _startup_time_from_coordinator(self) -> datetime | None:
        """Return the current startup timestamp derived from router uptime."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        if node is None:
            return None

        try:
            current_uptime = int(node.uptime)
        except (ValueError, TypeError):
            return None

        if current_uptime <= 0:
            return None

        return dt_util.now() - timedelta(seconds=current_uptime)

    def _sync_native_value(self) -> None:
        """Refresh the cached timestamp from coordinator data."""
        new_startup_time = self._startup_time_from_coordinator()
        if self._uptime_value_changed(self._attr_native_value, new_startup_time):
            self._attr_native_value = new_startup_time
        elif new_startup_time is None:
            self._attr_native_value = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_native_value()
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
        node = self.coordinator.data.get_node_by_id(self._node_id)
        if node is None:
            return {}

        return {
            "device_name": node.device_name,
            "serial_number": node.serial,
            "last_update": node.update_date,
        }


class TwibiRouterSerialSensor(TwibiBaseSensor):
    """Router serial number sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_serial_{full_serial[-4:]}", "Serial Number")
        self._node_id = node_id
        self._is_primary = is_primary
        # Override device info for proper assignment
        if not is_primary:
            runtime_data = get_runtime_data(
                coordinator.hass,
                coordinator.config_entry.entry_id,
            )
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (
                    DOMAIN,
                    runtime_data.primary_device_identifier,
                ),
            }

    @property
    def native_value(self) -> str | None:
        """Return the router serial number."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        return node.serial if node else None


class TwibiRouterLinkQualitySensor(TwibiBaseSensor):
    """Router link quality sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str, node_id: str, is_primary: bool, serial_suffix: str, full_serial: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, f"router_link_quality_{full_serial[-4:]}", "Link Quality")
        self._node_id = node_id
        self._is_primary = is_primary
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        # Override device info for proper assignment
        if not is_primary:
            runtime_data = get_runtime_data(
                coordinator.hass,
                coordinator.config_entry.entry_id,
            )
            self._attr_device_info = {
                "identifiers": {(DOMAIN, device_identifier)},
                "name": f"Twibi Router Secondary {device_identifier[-4:]}",
                "manufacturer": "Intelbras",
                "model": "Twibi Router",
                "via_device": (
                    DOMAIN,
                    runtime_data.primary_device_identifier,
                ),
            }

    @property
    def native_value(self) -> int | None:
        """Return the link quality."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        if node and node.link_quality is not None:
            try:
                return int(node.link_quality)
            except (ValueError, TypeError):
                return None
        return None


class TwibiConnectedDevicesSensor(TwibiBaseSensor):
    """Connected devices count sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "connected_devices",
            "Connected Devices",
        )
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the number of connected devices."""
        return len(self.coordinator.data.online_list)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        device_list = [
            {
                "name": device.display_name,
                "mac": device.mac,
                "ip": device.ip,
                "connection": device.connection_type,
            }
            for device in self.coordinator.data.online_list
        ]
        return {"devices": device_list}


class TwibiNetworkStatusSensor(TwibiBaseSensor):
    """Network status sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "network_status", "Network Status")
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(RouterConnectionState)

    @property
    def native_value(self) -> str:
        """Return the network status."""
        primary_node = self.coordinator.get_primary_node()
        if not primary_node:
            return RouterConnectionState.UNKNOWN

        return (
            RouterConnectionState.CONNECTED
            if primary_node.net_status is NodeNetworkStatus.CONNECTED
            else RouterConnectionState.DISCONNECTED
        )


class TwibiLanInfoSensor(TwibiBaseSensor):
    """LAN information sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "lan_info", "LAN Information")

    @property
    def native_value(self) -> str:
        """Return the LAN IP address."""
        lan_info = self.coordinator.data.lan_info
        return lan_info.lan_ip if lan_info else ""

    @property
    def available(self) -> bool:
        """Return whether LAN data is currently available."""
        return self.coordinator.last_update_success and self.coordinator.data.lan_info is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        lan_info = self.coordinator.data.lan_info
        if lan_info is None:
            return {}

        return {
            "subnet_mask": lan_info.lan_mask,
            "dhcp_enabled": lan_info.dhcp_enabled,
            "dhcp_start": lan_info.start_ip,
            "dhcp_end": lan_info.end_ip,
            "lease_time": lan_info.lease_time,
            "dns1": lan_info.dns1,
            "dns2": lan_info.dns2,
        }


class TwibiWanInfoSensor(TwibiBaseSensor):
    """WAN information sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "wan_info", "WAN Information")

    @property
    def native_value(self) -> str:
        """Return the WAN IP address."""
        if self.coordinator.data.wan_info:
            return self.coordinator.data.wan_info[0].ip
        return ""

    @property
    def available(self) -> bool:
        """Return whether WAN data is currently available."""
        return self.coordinator.last_update_success and bool(self.coordinator.data.wan_info)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if self.coordinator.data.wan_info:
            info = self.coordinator.data.wan_info[0]
            return {
                "netmask": info.netmask,
                "gateway": info.gateway,
                "mac": info.mac,
                "dns1": info.first_dns,
                "dns2": info.second_dns,
                "ipv6": info.ipv6,
            }
        return {}


class TwibiWifiQRCodeSensor(TwibiBaseSensor):
    """WiFi QR Code sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "wifi_qr_code", "WiFi QR Code")
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return the WiFi QR code string."""
        wifi_info = self.coordinator.data.wifi
        if wifi_info is None:
            return ""

        ssid = wifi_info.ssid
        password = wifi_info.password
        security = wifi_info.security_mode

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
    def available(self) -> bool:
        """Return whether WiFi data is currently available."""
        return self.coordinator.last_update_success and self.coordinator.data.wifi is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        wifi_info = self.coordinator.data.wifi
        if wifi_info is None:
            return {}

        return {
            "ssid": wifi_info.ssid,
            "security": wifi_info.security_mode,
            "type": wifi_info.security_type,
            "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
        }


class TwibiGuestWifiQRCodeSensor(TwibiBaseSensor):
    """Guest WiFi QR Code sensor."""

    def __init__(self, coordinator: TwibiCoordinator, device_identifier: str) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "guest_wifi_qr_code",
            "Guest WiFi QR Code",
        )
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        """Return the Guest WiFi QR code string."""
        guest_info = self.coordinator.data.guest_info
        if guest_info is None:
            return ""

        ssid = guest_info.ssid
        password = guest_info.password
        enabled = guest_info.enabled

        if not ssid or not enabled:
            return ""

        # Generate Guest WiFi QR code string
        if password:
            qr_string = f"WIFI:T:WPA;S:{ssid};P:{password};;"
        else:
            qr_string = f"WIFI:T:nopass;S:{ssid};;"

        return qr_string

    @property
    def available(self) -> bool:
        """Return whether guest WiFi data is currently available."""
        return self.coordinator.last_update_success and self.coordinator.data.guest_info is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        guest_info = self.coordinator.data.guest_info
        if guest_info is None:
            return {}

        return {
            "ssid": guest_info.ssid,
            "enabled": guest_info.enabled,
            "time_limit": guest_info.time_restriction,
            "bandwidth_limit": guest_info.bandwidth_limit,
            "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
        }
