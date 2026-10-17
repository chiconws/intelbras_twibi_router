"""Polls the router and shares one snapshot with every entity."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RouterData, TwibiAuthError, TwibiClient, TwibiError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type TwibiConfigEntry = ConfigEntry[TwibiCoordinator]


class TwibiCoordinator(DataUpdateCoordinator[RouterData]):
    """Fetch the router state every SCAN_INTERVAL."""

    config_entry: TwibiConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TwibiConfigEntry, client: TwibiClient) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.client = client

    async def _async_update_data(self) -> RouterData:
        try:
            return await self.client.async_get_data()
        except TwibiAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except TwibiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
