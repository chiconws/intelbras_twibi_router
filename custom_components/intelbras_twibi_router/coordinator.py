"""Coordinator for the Intelbras Twibi router integration."""
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

class TwibiCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Intelbras Twibi router."""

    async def _async_update_data(self):
        """Fetch data from API with proper error handling."""
        try:
            return await self.update_method()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
