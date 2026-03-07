"""Runtime data helpers for the Twibi integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import TwibiCoordinator
    from .twibi_api import TwibiAPI


@dataclass(slots=True)
class TwibiRuntimeData:
    """Typed runtime data stored in hass.data for a config entry."""

    api: TwibiAPI
    coordinator: TwibiCoordinator
    host: str
    primary_device_identifier: str


def get_runtime_data(hass: HomeAssistant, entry_id: str) -> TwibiRuntimeData:
    """Return typed runtime data for a config entry."""
    return cast(TwibiRuntimeData, hass.data[DOMAIN][entry_id])
