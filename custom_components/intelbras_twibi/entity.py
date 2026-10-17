"""Base entity: every entity belongs to one mesh node."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Node, TwibiError
from .const import DOMAIN, MANUFACTURER
from .coordinator import TwibiCoordinator


def node_device_info(node: Node, via_device_id: str | None = None) -> DeviceInfo:
    """Describe a mesh unit for the device registry."""
    info = DeviceInfo(
        identifiers={(DOMAIN, node.serial)},
        connections={(CONNECTION_NETWORK_MAC, node.mac)} if node.mac else set(),
        manufacturer=MANUFACTURER,
        model=node.model,
        name=f"{node.model} {node.serial[-4:]}",
        serial_number=node.serial,
        sw_version=node.firmware,
        configuration_url=f"http://{node.ip}" if node.ip else None,
    )
    if via_device_id and not node.is_primary:
        info["via_device_id"] = via_device_id
    return info


class TwibiEntity(CoordinatorEntity[TwibiCoordinator]):
    """Entity attached to a Twibi node's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TwibiCoordinator, serial: str, key: str) -> None:
        """Link the entity to the node with this serial."""
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_translation_key = key
        node = next(n for n in coordinator.data.nodes if n.serial == serial)
        self._attr_device_info = node_device_info(node, coordinator.primary_device_id)

    @property
    def node(self) -> Node | None:
        """Return this entity's node in the latest snapshot."""
        return next((n for n in self.coordinator.data.nodes if n.serial == self._serial), None)

    @property
    def available(self) -> bool:
        """Unavailable while the node is missing from the mesh."""
        return super().available and self.node is not None

    async def _async_command(self, command: Awaitable[None], refresh: bool = True) -> None:
        """Run a router command, surfacing failures to the user."""
        try:
            await command
        except TwibiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if refresh:
            await self.coordinator.async_request_refresh()
