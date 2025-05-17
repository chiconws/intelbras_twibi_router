"""Coordinator for the Intelbras Twibi router integration."""
import asyncio
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APIError
from .const import MAIN_SCHEMA

_LOGGER = logging.getLogger(__name__)

class TwibiCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Intelbras Twibi router."""

    async def _async_update_data(self):
        """Update data from the router with retry logic."""
        max_retries = 3
        retry_delay = 10

        for attempt in range(max_retries):
            try:
                data = await self.update_method()
                _LOGGER.debug("Data fetched successfully: %s", data)
                _LOGGER.debug("Data validation: %s", MAIN_SCHEMA(data))
                return MAIN_SCHEMA(data)

            except APIError as err:
                if attempt < max_retries - 1:
                    self.logger.warning(
                        "Update failed (attempt %d/%d): %s. Retrying...",
                        attempt + 1,
                        max_retries,
                        err
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                raise UpdateFailed(f"Update failed after {max_retries} attempts: {err}") from err

        return None
