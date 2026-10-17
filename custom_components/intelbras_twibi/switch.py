"""Switches: guest Wi-Fi and UPnP."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RouterData, TwibiClient
from .coordinator import TwibiConfigEntry, TwibiCoordinator
from .entity import TwibiEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class TwibiSwitchDescription(SwitchEntityDescription):
    """How to read and write one router setting."""

    is_on_fn: Callable[[RouterData], bool | None]
    set_fn: Callable[[TwibiClient, RouterData, bool], Awaitable[None]]


SWITCHES = (
    TwibiSwitchDescription(
        key="guest_wifi",
        is_on_fn=lambda d: d.guest.enabled if d.guest else None,
        set_fn=lambda c, d, on: c.async_set_guest(d.guest, on),  # type: ignore[arg-type]  # only created when guest is reported
    ),
    TwibiSwitchDescription(
        key="upnp",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: d.upnp_enabled,
        set_fn=lambda c, d, on: c.async_set_upnp(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TwibiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the switches the router reports."""
    coordinator = entry.runtime_data
    primary = coordinator.data.primary.serial
    async_add_entities(
        TwibiSwitch(coordinator, primary, desc)
        for desc in SWITCHES
        if desc.is_on_fn(coordinator.data) is not None
    )


class TwibiSwitch(TwibiEntity, SwitchEntity):
    """A router setting that is on or off."""

    entity_description: TwibiSwitchDescription

    def __init__(
        self, coordinator: TwibiCoordinator, serial: str, description: TwibiSwitchDescription
    ) -> None:
        """Bind the description."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Unavailable when the router stops reporting this setting."""
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        """Read the setting from the latest snapshot."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self._set(False)

    async def _set(self, on: bool) -> None:
        await self._async_command(self.entity_description.set_fn(self.coordinator.client, self.coordinator.data, on))
