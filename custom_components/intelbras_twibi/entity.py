"""Base entity: every entity belongs to one mesh node."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Node, TwibiError
from .const import DOMAIN, MANUFACTURER
from .coordinator import TwibiCoordinator


class TwibiEntity(CoordinatorEntity[TwibiCoordinator]):
    """Entity attached to a Twibi node's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TwibiCoordinator, serial: str, key: str) -> None:
        """Link the entity to the node with this serial."""
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_translation_key = key
        node = self.node
        primary = coordinator.data.primary
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            connections={(CONNECTION_NETWORK_MAC, node.mac)} if node and node.mac else set(),
            manufacturer=MANUFACTURER,
            model=node.model if node else None,
            name=f"{node.model if node else 'Twibi'} {serial[-4:]}",
            serial_number=serial,
            sw_version=node.firmware if node else None,
            configuration_url=f"http://{node.ip}" if node and node.ip else None,
            via_device=None if serial == primary.serial else (DOMAIN, primary.serial),
        )

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
