"""Improved coordinator for the Intelbras Twibi router integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APIError, AuthenticationError, ConnectionError as TwibiConnectionError
from .api_v2 import TwibiAPI
from .const import MAIN_SCHEMA

_LOGGER = logging.getLogger(__name__)


class TwibiCoordinator(DataUpdateCoordinator):
    """Improved data update coordinator for Intelbras Twibi router."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger,
        name: str,
        api: TwibiAPI,
        update_interval: timedelta,
        max_retries: int = 3,
        base_retry_delay: int = 5,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, logger, name=name, update_interval=update_interval)
        self.api = api
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self._consecutive_failures = 0
        self._last_successful_update = None
        self._router_restart_detected = False
        self._restart_recovery_attempts = 0
        self._max_restart_recovery_attempts = 10  # Allow more attempts during restart recovery

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from the router with improved retry logic and error handling."""
        # Check if we're in restart recovery mode
        max_attempts = self._max_restart_recovery_attempts if self._router_restart_detected else self.max_retries

        for attempt in range(max_attempts):
            try:
                # Perform health check first if we've had recent failures
                if self._consecutive_failures > 0:
                    health_ok = await self.api.health_check()
                    if not health_ok:
                        raise TwibiConnectionError("Health check failed")

                # Fetch data using split API calls to reduce instability
                # Start with basic modules that should always work
                data = await self.api.get_modules(["node_info", "online_list", "wan_statistic"])

                # Try to fetch extended modules one by one to avoid overloading the router
                extended_modules = ["wan_info", "lan_info", "wifi", "guest_info", "upnp_info"]
                for module in extended_modules:
                    try:
                        extended_data = await self.api.get_modules([module])
                        data.update(extended_data)
                        # Small delay between requests to avoid overwhelming the router
                        await asyncio.sleep(0.1)
                    except Exception:
                            # Continue with other modules even if one fails
                        continue

                # Validate data structure
                validated_data = MAIN_SCHEMA(data)

                # Check for router restart detection
                if self._detect_router_restart(validated_data):
                    _LOGGER.info("Router restart detected - entering recovery mode")
                    self._router_restart_detected = True
                    self._restart_recovery_attempts = 0

                # Reset failure counters on success
                self._consecutive_failures = 0
                self._last_successful_update = self.hass.loop.time()

                # Reset restart detection if we've been successful for a while
                if self._router_restart_detected and self._restart_recovery_attempts > 3:
                    _LOGGER.info("Router restart recovery completed")
                    self._router_restart_detected = False
                    self._restart_recovery_attempts = 0

                return validated_data

            except AuthenticationError as err:
                # Authentication errors might be temporary with flaky routers
                self._consecutive_failures += 1
                self.api.invalidate_auth()

                if attempt < self.max_retries - 1:
                    # For flaky routers, try to re-authenticate
                    delay = self.base_retry_delay * (2 ** attempt)
                    self.logger.warning(
                        "Authentication failed (attempt %d/%d): %s. Router may be unstable, retrying in %d seconds...",
                        attempt + 1,
                        self.max_retries,
                        err,
                        delay
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    self.logger.error(
                        "Authentication failed after %d attempts: %s. Router may be unstable.",
                        self.max_retries,
                        err
                    )
                    raise UpdateFailed(f"Authentication failed after {self.max_retries} attempts: {err}") from err

            except (TwibiConnectionError, APIError) as err:
                self._consecutive_failures += 1

                # Check if this might be a router restart (daily 03:30 restart)
                current_time = self.hass.loop.time()
                if (self._last_successful_update is not None and
                    (current_time - self._last_successful_update) < 600 and  # Less than 10 minutes since last success
                    not self._router_restart_detected):
                    _LOGGER.info("Possible router restart detected - enabling extended recovery mode")
                    self._router_restart_detected = True
                    self._restart_recovery_attempts = 0

                if attempt < max_attempts - 1:
                    # Calculate delay - use longer delays during restart recovery
                    if self._router_restart_detected:
                        # During restart recovery, use longer delays to give router time to boot
                        delay = min(30, self.base_retry_delay * (2 ** min(attempt, 4)))  # Cap at 30 seconds
                        self._restart_recovery_attempts += 1
                    else:
                        delay = self.base_retry_delay * (2 ** attempt)

                    self.logger.warning(
                        "Update failed (attempt %d/%d): %s. %sRetrying in %d seconds...",
                        attempt + 1,
                        max_attempts,
                        err,
                        "Router restart recovery mode - " if self._router_restart_detected else "",
                        delay
                    )

                    await asyncio.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    if self._router_restart_detected:
                        self.logger.error(
                            "Update failed after %d restart recovery attempts: %s. Router may still be restarting.",
                            max_attempts,
                            err
                        )
                        # Don't reset restart detection immediately - let it persist for next update cycle
                    else:
                        self.logger.error(
                            "Update failed after %d attempts: %s",
                            max_attempts,
                            err
                        )
                    raise UpdateFailed(f"Update failed after {max_attempts} attempts: {err}") from err

            except Exception as err:
                # Unexpected errors
                self._consecutive_failures += 1
                self.logger.error("Unexpected error during update: %s", err)

                if attempt < self.max_retries - 1:
                    delay = self.base_retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise UpdateFailed(f"Unexpected error after {self.max_retries} attempts: {err}") from err

        # This should never be reached, but just in case
        raise UpdateFailed("Maximum retries exceeded")

    async def async_refresh_with_fallback(self) -> bool:
        """Attempt to refresh data with fallback to cached data if available."""
        try:
            await self.async_refresh()
        except UpdateFailed:
            # If we have recent cached data, continue using it
            if (
                self.data is not None
                and self._last_successful_update is not None
                and (self.hass.loop.time() - self._last_successful_update) < 300  # 5 minutes
            ):
                _LOGGER.warning("Using cached data due to update failure")
                return True
            return False

        return True

    @property
    def connection_status(self) -> str:
        """Get current connection status."""
        if self.last_update_success:
            return "connected"
        if self._consecutive_failures == 1:
            return "reconnecting"
        if self._consecutive_failures < self.max_retries:
            return "unstable"
        return "disconnected"

    @property
    def has_recent_data(self) -> bool:
        """Check if we have recent data available."""
        return (
            self.data is not None
            and self._last_successful_update is not None
            and (self.hass.loop.time() - self._last_successful_update) < 600  # 10 minutes
        )

    async def async_set_led_status(self, serial: str, enabled: bool) -> bool:
        """Set LED status and refresh data."""
        try:
            success = await self.api.set_led_status(serial, enabled)
            if success:
                # Refresh data after successful command
                await asyncio.sleep(1)  # Brief delay for router to process
                await self.async_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set LED status: %s", err)
            return False

        return success

    async def async_restart_router(self) -> bool:
        """Restart router."""
        try:
            success = await self.api.restart_router()
            if success:
                # Don't refresh immediately after restart as router will be rebooting
                _LOGGER.info("Router restart command sent successfully")
        except Exception as err:
            _LOGGER.error("Failed to restart router: %s", err)
            return False

        return success

    async def async_get_device_info(self, mac: str) -> dict[str, Any] | None:
        """Get specific device information."""
        try:
            return await self.api.get_device_by_mac(mac)
        except Exception as err:
            _LOGGER.error("Failed to get device info for %s: %s", mac, err)
            return None

    def get_node_by_serial(self, serial: str) -> dict[str, Any] | None:
        """Get node information by serial number from cached data."""
        if not self.data or "node_info" not in self.data:
            return None

        return next(
            (node for node in self.data["node_info"] if node.get("sn") == serial),
            None
        )

    def get_device_by_mac(self, mac: str) -> dict[str, Any] | None:
        """Get device information by MAC address from cached data."""
        if not self.data or "online_list" not in self.data:
            return None

        return next(
            (device for device in self.data["online_list"] if device.get("dev_mac") == mac),
            None
        )

    def get_primary_node(self) -> dict[str, Any] | None:
        """Get primary node from cached data."""
        if not self.data or "node_info" not in self.data:
            return None

        return next(
            (node for node in self.data["node_info"] if node.get("role") == "1"),
            None
        )

    def get_wan_statistics(self) -> dict[str, Any] | None:
        """Get WAN statistics from cached data."""
        if not self.data or "wan_statistic" not in self.data:
            return None

        wan_stats = self.data["wan_statistic"]
        return wan_stats[0] if wan_stats else None

    def _detect_router_restart(self, new_data: dict[str, Any] | None) -> bool:
        """Detect if router has restarted by comparing uptime values."""
        if not self.data or "node_info" not in self.data or "node_info" not in new_data:
            return False

        # Compare uptime values for primary router
        old_nodes = {node.get("sn"): node for node in self.data.get("node_info", [])}
        new_nodes = {node.get("sn"): node for node in new_data.get("node_info", [])}

        for serial, new_node in new_nodes.items():
            if serial in old_nodes:
                old_uptime = int(old_nodes[serial].get("Uptime", 0))
                new_uptime = int(new_node.get("Uptime", 0))

                # If new uptime is significantly less than old uptime, router restarted
                if old_uptime > 0 and new_uptime < old_uptime and (old_uptime - new_uptime) > 60:
                    return True

        return False

    @property
    def is_restart_recovery_mode(self) -> bool:
        """Check if coordinator is in restart recovery mode."""
        return self._router_restart_detected

    async def async_force_restart_recovery(self) -> None:
        """Manually trigger restart recovery mode (useful for testing or manual recovery)."""
        _LOGGER.info("Manually triggering restart recovery mode")
        self._router_restart_detected = True
        self._restart_recovery_attempts = 0
        self._consecutive_failures = 0
