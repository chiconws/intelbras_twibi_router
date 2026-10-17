"""Sensors: WAN throughput, client count, WAN IP, node uptime and mesh link."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Node, RouterData
from .coordinator import TwibiConfigEntry, TwibiCoordinator
from .entity import TwibiEntity

PARALLEL_UPDATES = 0
# The router reports uptime with a few seconds of jitter; ignore drifts below this.
UPTIME_TOLERANCE = timedelta(minutes=2)


@dataclass(frozen=True, kw_only=True)
class TwibiRouterSensorDescription(SensorEntityDescription):
    """A sensor on the primary node, read from the whole snapshot."""

    value_fn: Callable[[RouterData], float | int | str | None]


ROUTER_SENSORS = (
    TwibiRouterSensorDescription(
        key="wan_download",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        value_fn=lambda d: d.wan_download,
    ),
    TwibiRouterSensorDescription(
        key="wan_upload",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        value_fn=lambda d: d.wan_upload,
    ),
    TwibiRouterSensorDescription(
        key="connected_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: len(d.clients),
    ),
    TwibiRouterSensorDescription(
        key="wan_ip",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.wan_ip,
    ),
)

# Firmware 1.1.10 reports dBm (-82), 1.1.11 a small level (1), so no unit is claimed.
LINK_QUALITY = SensorEntityDescription(
    key="link_quality",
    state_class=SensorStateClass.MEASUREMENT,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the router and per-node sensors."""
    coordinator = entry.runtime_data
    primary = coordinator.data.primary.serial
    entities: list[SensorEntity] = [
        TwibiRouterSensor(coordinator, primary, desc) for desc in ROUTER_SENSORS
    ]
    for node in coordinator.data.nodes:
        entities.append(TwibiUptimeSensor(coordinator, node.serial))
        if not node.is_primary:
            entities.append(TwibiLinkQualitySensor(coordinator, node.serial))
    async_add_entities(entities)


class TwibiRouterSensor(TwibiEntity, SensorEntity):
    """Router-wide value shown on the primary node."""

    entity_description: TwibiRouterSensorDescription

    def __init__(
        self, coordinator: TwibiCoordinator, serial: str, description: TwibiRouterSensorDescription
    ) -> None:
        """Bind the description."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        """Read the value from the latest snapshot."""
        return self.entity_description.value_fn(self.coordinator.data)


class TwibiLinkQualitySensor(TwibiEntity, SensorEntity):
    """Mesh backhaul signal of a secondary node."""

    entity_description = LINK_QUALITY

    def __init__(self, coordinator: TwibiCoordinator, serial: str) -> None:
        """Bind to the node."""
        super().__init__(coordinator, serial, LINK_QUALITY.key)

    @property
    def native_value(self) -> int | None:
        """Return the link quality as the router reports it."""
        node = self.node
        return node.link_quality if node else None


class TwibiUptimeSensor(TwibiEntity, SensorEntity):
    """When the node last booted."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: TwibiCoordinator, serial: str) -> None:
        """Bind to the node."""
        super().__init__(coordinator, serial, "last_boot")
        self._boot: datetime | None = None

    @property
    def native_value(self) -> datetime | None:
        """Return the boot time, stable across polls."""
        node: Node | None = self.node
        if node is None or not node.uptime:
            return None
        boot = dt_util.utcnow().replace(microsecond=0) - timedelta(seconds=node.uptime)
        if self._boot is None or abs(boot - self._boot) > UPTIME_TOLERANCE:
            self._boot = boot
        return self._boot
