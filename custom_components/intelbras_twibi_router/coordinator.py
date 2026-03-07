"""Improved coordinator for the Intelbras Twibi router integration."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import APIError, AuthenticationError, ConnectionError as TwibiConnectionError
from .api.models import NodeInfo, OnlineDevice, RouterData, WanStatistic
from .const import MAIN_SCHEMA
from .twibi_api import TwibiAPI

_LOGGER = logging.getLogger(__name__)


class TwibiCoordinator(DataUpdateCoordinator[RouterData]):
    """Improved data update coordinator for Intelbras Twibi router."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger,
        config_entry: ConfigEntry,
        name: str,
        api: TwibiAPI,
        update_interval: timedelta,
        max_retries: int = 3,
        base_retry_delay: int = 5,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.api = api
        self.known_macs: set[str] = set()
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay
        self._consecutive_failures = 0
        self._last_successful_update = None
        self._router_restart_detected = False
        self._restart_recovery_attempts = 0
        self._max_restart_recovery_attempts = 10  # Allow more attempts during restart recovery

    async def _async_update_data(self) -> RouterData:
        """Update data from the router with improved retry logic and error handling."""
        for attempt in range(self._max_restart_recovery_attempts):
            max_attempts = self._current_max_attempts()
            if attempt >= max_attempts:
                break

            try:
                # Perform health check first if we've had recent failures
                if self._consecutive_failures > 0:
                    health_ok = await self.api.health_check()
                    if not health_ok:
                        raise TwibiConnectionError("Health check failed")

                # Fetch data using split API calls to reduce instability
                # Start with basic modules that should always work
                data = await self.api.get_data(["node_info", "online_list", "wan_statistic"])

                # Try to fetch extended modules one by one to avoid overloading the router
                extended_modules = ["wan_info", "lan_info", "wifi", "guest_info", "upnp_info"]
                for module in extended_modules:
                    try:
                        extended_data = await self.api.get_data([module])
                        data.update(extended_data)
                        # Small delay between requests to avoid overwhelming the router
                        await asyncio.sleep(0.1)
                    except Exception:
                            # Continue with other modules even if one fails
                        continue

                # Validate data structure
                validated_data = MAIN_SCHEMA(data)
                typed_data = RouterData.from_dict(
                    validated_data,
                    exclude_wired=self.api.exclude_wired,
                )

                # Check for router restart detection
                if self._detect_router_restart(typed_data):
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

                return typed_data

            except AuthenticationError as err:
                # Authentication errors might be temporary with flaky routers
                self._consecutive_failures += 1
                self.api.invalidate_auth()
                self._maybe_enable_restart_recovery()
                max_attempts = self._current_max_attempts()

                if attempt < max_attempts - 1:
                    # For flaky routers, try to re-authenticate
                    delay = self._get_retry_delay(attempt)
                    self._record_retry_attempt()
                    self.logger.warning(
                        "Authentication failed (attempt %d/%d): %s. %sRetrying in %d seconds...",
                        attempt + 1,
                        max_attempts,
                        err,
                        "Router restart recovery mode - " if self._router_restart_detected else "",
                        delay
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    self.logger.error(
                        "Authentication failed after %d attempts: %s. Router may be unstable.",
                        max_attempts,
                        err
                    )
                    raise UpdateFailed(f"Authentication failed after {max_attempts} attempts: {err}") from err

            except (TwibiConnectionError, APIError) as err:
                self._consecutive_failures += 1

                # Check if this might be a router restart (daily 03:30 restart)
                self._maybe_enable_restart_recovery()
                max_attempts = self._current_max_attempts()

                if attempt < max_attempts - 1:
                    delay = self._get_retry_delay(attempt)
                    self._record_retry_attempt()

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
                self._maybe_enable_restart_recovery()
                max_attempts = self._current_max_attempts()
                self.logger.error("Unexpected error during update: %s", err)

                if attempt < max_attempts - 1:
                    delay = self._get_retry_delay(attempt)
                    self._record_retry_attempt()
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise UpdateFailed(f"Unexpected error after {max_attempts} attempts: {err}") from err

        # This should never be reached, but just in case
        raise UpdateFailed("Maximum retries exceeded")

    def _current_max_attempts(self) -> int:
        """Return the active retry limit for the current update cycle."""
        return (
            self._max_restart_recovery_attempts
            if self._router_restart_detected
            else self.max_retries
        )

    def _maybe_enable_restart_recovery(self) -> None:
        """Enable restart recovery mode when a recent-success failure suggests a reboot."""
        if self._router_restart_detected or self._last_successful_update is None:
            return

        current_time = self.hass.loop.time()
        if (current_time - self._last_successful_update) < 600:
            _LOGGER.info("Possible router restart detected - enabling extended recovery mode")
            self._router_restart_detected = True
            self._restart_recovery_attempts = 0

    def _get_retry_delay(self, attempt: int) -> int:
        """Return the retry delay for the current mode."""
        if self._router_restart_detected:
            # During restart recovery, use longer delays to give router time to boot.
            return min(30, self.base_retry_delay * (2 ** min(attempt, 4)))

        return self.base_retry_delay * (2 ** attempt)

    def _record_retry_attempt(self) -> None:
        """Track retry attempts during restart recovery."""
        if self._router_restart_detected:
            self._restart_recovery_attempts += 1

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
        max_attempts = self._current_max_attempts()

        if self.last_update_success:
            return "connected"
        if self._consecutive_failures == 1:
            return "reconnecting"
        if self._consecutive_failures < max_attempts:
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

    async def async_get_device_info(self, mac: str) -> OnlineDevice | None:
        """Get specific device information."""
        try:
            return await self.api.get_device_by_mac(mac)
        except Exception as err:
            _LOGGER.error("Failed to get device info for %s: %s", mac, err)
            return None

    def get_node_by_serial(self, serial: str) -> NodeInfo | None:
        """Get node information by serial number from cached data."""
        if not self.data:
            return None

        return self.data.get_node_by_serial(serial)

    def get_device_by_mac(self, mac: str) -> OnlineDevice | None:
        """Get device information by MAC address from cached data."""
        if not self.data:
            return None

        return self.data.get_device_by_mac(mac)

    def get_primary_node(self) -> NodeInfo | None:
        """Get primary node from cached data."""
        if not self.data:
            return None

        return self.data.primary_node

    def get_wan_statistics(self) -> WanStatistic | None:
        """Get WAN statistics from cached data."""
        if not self.data or not self.data.wan_statistic:
            return None

        return self.data.wan_statistic[0]

    def _detect_router_restart(self, new_data: RouterData | None) -> bool:
        """Detect if router has restarted by comparing uptime values."""
        if not self.data or not new_data:
            return False

        # Compare uptime values for primary router
        old_nodes = {node.serial: node for node in self.data.node_info}
        new_nodes = {node.serial: node for node in new_data.node_info}

        for serial, new_node in new_nodes.items():
            if serial in old_nodes:
                old_uptime = self._parse_uptime(old_nodes[serial].uptime)
                new_uptime = self._parse_uptime(new_node.uptime)
                if old_uptime is None or new_uptime is None:
                    continue

                # If new uptime is significantly less than old uptime, router restarted
                if old_uptime > 0 and new_uptime < old_uptime and (old_uptime - new_uptime) > 60:
                    return True

        return False

    @staticmethod
    def _parse_uptime(value: str) -> int | None:
        """Safely parse uptime values returned by the router."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
