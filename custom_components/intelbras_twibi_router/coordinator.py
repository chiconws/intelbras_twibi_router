"""Coordinator for the Intelbras Twibi router integration."""
import asyncio

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APIError


class TwibiCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Intelbras Twibi router."""

    async def _async_update_data(self):
        """Update data from the router with retry logic."""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                return await self.update_method()
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
