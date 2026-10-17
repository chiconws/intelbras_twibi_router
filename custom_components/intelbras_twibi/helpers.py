"""Shared entity helpers for the Twibi integration."""

from homeassistant.helpers.device_registry import DeviceInfo

from .api.models import NodeInfo
from .const import DOMAIN


def get_node_device_identifier(
    node: NodeInfo,
    primary_device_identifier: str,
) -> str:
    """Return the device identifier used for a router node entity."""
    return primary_device_identifier if node.is_primary else node.serial


def build_router_device_info(device_identifier: str) -> DeviceInfo:
    """Build device info for an entity attached to an existing router device."""
    return DeviceInfo(identifiers={(DOMAIN, device_identifier)})
