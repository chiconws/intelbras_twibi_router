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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api.enums import NodeNetworkStatus, RouterConnectionState
from .coordinator import TwibiCoordinator
from .helpers import build_router_device_info, get_node_device_identifier
from .runtime_data import get_runtime_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Twibi Router sensor entities."""
    runtime_data = get_runtime_data(hass, entry.entry_id)
    coordinator = runtime_data.coordinator
    primary_device_identifier = runtime_data.primary_device_identifier

    entities: list[TwibiBaseSensor] = []

    if coordinator.data.wan_statistic:
        for wan_stat in coordinator.data.wan_statistic:
            entities.extend(
                [
                    TwibiWanUploadSpeedSensor(
                        coordinator,
                        primary_device_identifier,
                        wan_stat.id,
                    ),
                    TwibiWanDownloadSpeedSensor(
                        coordinator,
                        primary_device_identifier,
                        wan_stat.id,
                    ),
                ]
            )

    for node in coordinator.data.node_info:
        device_identifier = get_node_device_identifier(
            node,
            primary_device_identifier,
        )

        entities.extend(
            [
                TwibiRouterUptimeSensor(
                    coordinator,
                    device_identifier,
                    node.id,
                    node.serial,
                ),
                TwibiRouterSerialSensor(
                    coordinator,
                    device_identifier,
                    node.id,
                    node.serial,
                ),
            ]
        )

        if not node.is_primary:
            entities.append(
                TwibiRouterLinkQualitySensor(
                    coordinator,
                    device_identifier,
                    node.id,
                    node.serial,
                )
            )

    entities.extend(
        [
            TwibiConnectedDevicesSensor(coordinator, primary_device_identifier),
            TwibiNetworkStatusSensor(coordinator, primary_device_identifier),
            TwibiLanInfoSensor(coordinator, primary_device_identifier),
            TwibiWanInfoSensor(coordinator, primary_device_identifier),
            TwibiWifiQRCodeSensor(coordinator, primary_device_identifier),
            TwibiGuestWifiQRCodeSensor(coordinator, primary_device_identifier),
        ]
    )

    async_add_entities(entities)


class TwibiBaseSensor(SensorEntity):
    """Base class for Twibi Router sensors."""

    coordinator: TwibiCoordinator

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.coordinator = coordinator
        self._attr_should_poll = False
        self._attr_available = coordinator.last_update_success
        self._attr_device_info = build_router_device_info(device_identifier)
        self._attr_name = name
        self._attr_unique_id = f"{device_identifier}_{sensor_type}"

    async def async_added_to_hass(self) -> None:
        """Register coordinator listener when the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh entity state when coordinator data changes."""
        self._update_from_coordinator()
        self.async_write_ha_state()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh cached attributes from coordinator data."""
        self._attr_available = self.coordinator.last_update_success


class TwibiWanUploadSpeedSensor(TwibiBaseSensor):
    """WAN upload speed sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        wan_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            f"wan_upload_speed_{wan_id}",
            "WAN Upload Speed",
        )
        self._wan_id = wan_id
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh upload speed from coordinator data."""
        super()._update_from_coordinator()
        statistic = self.coordinator.data.get_wan_statistic(self._wan_id)
        self._attr_native_value = statistic.up_speed_float if statistic else None


class TwibiWanDownloadSpeedSensor(TwibiBaseSensor):
    """WAN download speed sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        wan_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            f"wan_download_speed_{wan_id}",
            "WAN Download Speed",
        )
        self._wan_id = wan_id
        self._attr_device_class = SensorDeviceClass.DATA_RATE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfDataRate.KILOBITS_PER_SECOND
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh download speed from coordinator data."""
        super()._update_from_coordinator()
        statistic = self.coordinator.data.get_wan_statistic(self._wan_id)
        self._attr_native_value = statistic.down_speed_float if statistic else None


class TwibiRouterUptimeSensor(TwibiBaseSensor):
    """Router uptime sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        node_id: str,
        full_serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            f"router_uptime_{full_serial[-4:]}",
            "Uptime",
        )
        self._node_id = node_id
        self._startup_time: datetime | None = None
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._update_from_coordinator()

    def _startup_time_from_coordinator(self) -> datetime | None:
        """Return the current startup timestamp derived from router uptime."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        if node is None:
            return None

        try:
            current_uptime = int(node.uptime)
        except (TypeError, ValueError):
            return None

        if current_uptime <= 0:
            return None

        return dt_util.now() - timedelta(seconds=current_uptime)

    @staticmethod
    def _uptime_value_changed(
        old_value: datetime | None,
        new_value: datetime | None,
    ) -> bool:
        """Check if uptime value changed enough to warrant a state update."""
        if old_value is None or new_value is None:
            return old_value != new_value

        return (
            new_value != old_value
            and abs((new_value - old_value).total_seconds()) > 120
        )

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh uptime and metadata from coordinator data."""
        new_startup_time = self._startup_time_from_coordinator()
        if self._uptime_value_changed(self._startup_time, new_startup_time):
            self._startup_time = new_startup_time
        elif new_startup_time is None:
            self._startup_time = None

        node = self.coordinator.data.get_node_by_id(self._node_id)
        self._attr_native_value = self._startup_time
        self._attr_available = (
            self.coordinator.last_update_success and self._startup_time is not None
        )
        self._attr_extra_state_attributes = (
            {
                "device_name": node.device_name,
                "serial_number": node.serial,
                "last_update": node.update_date,
            }
            if node is not None
            else {}
        )


class TwibiRouterSerialSensor(TwibiBaseSensor):
    """Router serial number sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        node_id: str,
        full_serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            f"router_serial_{full_serial[-4:]}",
            "Serial Number",
        )
        self._node_id = node_id
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh node serial from coordinator data."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        self._attr_native_value = node.serial if node else None
        self._attr_available = self.coordinator.last_update_success and node is not None


class TwibiRouterLinkQualitySensor(TwibiBaseSensor):
    """Router link quality sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
        node_id: str,
        full_serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            f"router_link_quality_{full_serial[-4:]}",
            "Link Quality",
        )
        self._node_id = node_id
        self._attr_native_unit_of_measurement = "dBm"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh link quality from coordinator data."""
        node = self.coordinator.data.get_node_by_id(self._node_id)
        if node and node.link_quality is not None:
            try:
                self._attr_native_value = int(node.link_quality)
            except (TypeError, ValueError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None

        self._attr_available = self.coordinator.last_update_success and node is not None


class TwibiConnectedDevicesSensor(TwibiBaseSensor):
    """Connected devices count sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "connected_devices",
            "Connected Devices",
        )
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh connected device count from coordinator data."""
        super()._update_from_coordinator()
        self._attr_native_value = len(self.coordinator.data.online_list)
        self._attr_extra_state_attributes = {
            "devices": [
                {
                    "name": device.display_name,
                    "mac": device.mac,
                    "ip": device.ip,
                    "connection": device.connection_type,
                }
                for device in self.coordinator.data.online_list
            ]
        }


class TwibiNetworkStatusSensor(TwibiBaseSensor):
    """Network status sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "network_status",
            "Network Status",
        )
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = list(RouterConnectionState)
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh network status from coordinator data."""
        super()._update_from_coordinator()
        primary_node = self.coordinator.get_primary_node()
        self._attr_native_value = (
            RouterConnectionState.CONNECTED
            if primary_node and primary_node.net_status is NodeNetworkStatus.CONNECTED
            else RouterConnectionState.DISCONNECTED
            if primary_node
            else RouterConnectionState.UNKNOWN
        )


class TwibiLanInfoSensor(TwibiBaseSensor):
    """LAN information sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "lan_info", "LAN Information")
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh LAN information from coordinator data."""
        lan_info = self.coordinator.data.lan_info
        self._attr_native_value = lan_info.lan_ip if lan_info else None
        self._attr_available = (
            self.coordinator.last_update_success and lan_info is not None
        )
        self._attr_extra_state_attributes = (
            {
                "subnet_mask": lan_info.lan_mask,
                "dhcp_enabled": lan_info.dhcp_enabled,
                "dhcp_start": lan_info.start_ip,
                "dhcp_end": lan_info.end_ip,
                "lease_time": lan_info.lease_time,
                "dns1": lan_info.dns1,
                "dns2": lan_info.dns2,
            }
            if lan_info is not None
            else {}
        )


class TwibiWanInfoSensor(TwibiBaseSensor):
    """WAN information sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, device_identifier, "wan_info", "WAN Information")
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh WAN information from coordinator data."""
        info = self.coordinator.data.wan_info[0] if self.coordinator.data.wan_info else None
        self._attr_native_value = info.ip if info else None
        self._attr_available = self.coordinator.last_update_success and info is not None
        self._attr_extra_state_attributes = (
            {
                "netmask": info.netmask,
                "gateway": info.gateway,
                "mac": info.mac,
                "dns1": info.first_dns,
                "dns2": info.second_dns,
                "ipv6": info.ipv6,
            }
            if info is not None
            else {}
        )


class TwibiWifiQRCodeSensor(TwibiBaseSensor):
    """WiFi QR Code sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "wifi_qr_code",
            "WiFi QR Code",
        )
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh Wi-Fi QR code data from coordinator data."""
        wifi_info = self.coordinator.data.wifi
        self._attr_available = self.coordinator.last_update_success and wifi_info is not None
        self._attr_native_value = self._build_qr_code(wifi_info) if wifi_info else None
        self._attr_extra_state_attributes = (
            {
                "ssid": wifi_info.ssid,
                "security": wifi_info.security_mode,
                "type": wifi_info.security_type,
                "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
            }
            if wifi_info is not None
            else {}
        )

    @staticmethod
    def _build_qr_code(wifi_info: Any) -> str | None:
        """Build a QR code string for the main Wi-Fi network."""
        ssid = wifi_info.ssid
        if not ssid:
            return None

        security = wifi_info.security_mode
        auth_type = (
            "WPA"
            if "psk" in security.lower()
            else "nopass"
            if security.lower() == "none"
            else "WPA"
        )

        if auth_type == "nopass":
            return f"WIFI:T:nopass;S:{ssid};;"

        return f"WIFI:T:{auth_type};S:{ssid};P:{wifi_info.password};;"


class TwibiGuestWifiQRCodeSensor(TwibiBaseSensor):
    """Guest WiFi QR Code sensor."""

    def __init__(
        self,
        coordinator: TwibiCoordinator,
        device_identifier: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            device_identifier,
            "guest_wifi_qr_code",
            "Guest WiFi QR Code",
        )
        self._attr_icon = "mdi:qrcode"
        self._attr_entity_registry_enabled_default = False
        self._update_from_coordinator()

    @callback
    def _update_from_coordinator(self) -> None:
        """Refresh guest Wi-Fi QR code data from coordinator data."""
        guest_info = self.coordinator.data.guest_info
        self._attr_available = (
            self.coordinator.last_update_success and guest_info is not None
        )
        self._attr_native_value = (
            self._build_qr_code(guest_info) if guest_info else None
        )
        self._attr_extra_state_attributes = (
            {
                "ssid": guest_info.ssid,
                "enabled": guest_info.enabled,
                "time_limit": guest_info.time_restriction,
                "bandwidth_limit": guest_info.bandwidth_limit,
                "qr_format": "WIFI:T:WPA;S:SSID;P:PASSWORD;;",
            }
            if guest_info is not None
            else {}
        )

    @staticmethod
    def _build_qr_code(guest_info: Any) -> str | None:
        """Build a QR code string for the guest network."""
        if not guest_info.ssid or not guest_info.enabled:
            return None

        if guest_info.password:
            return f"WIFI:T:WPA;S:{guest_info.ssid};P:{guest_info.password};;"

        return f"WIFI:T:nopass;S:{guest_info.ssid};;"
