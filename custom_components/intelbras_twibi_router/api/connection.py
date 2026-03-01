"""Connection management for Twibi Router API."""

import asyncio
from datetime import datetime
import hashlib
import json
import logging
from typing import Any

import aiohttp

from ..const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class TwibiConnection:
    """Manages connection and authentication for Twibi Router."""

    def __init__(
        self,
        host: str,
        password: str,
        session: aiohttp.ClientSession,
        timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the connection manager."""
        self.host = host
        self._password = password
        self.session = session
        self.timeout = timeout
        self._authenticated = False
        self._auth_lock = asyncio.Lock()

    @property
    def base_url(self) -> str:
        """Return base URL for API endpoints."""
        return f"http://{self.host}/goform"

    @property
    def get_url(self) -> str:
        """Return GET endpoint URL."""
        return f"{self.base_url}/get?module_id="

    @property
    def set_url(self) -> str:
        """Return SET endpoint URL."""
        return f"{self.base_url}/set"

    @staticmethod
    def get_timestamp() -> int:
        """Get current timestamp in milliseconds."""
        return int(datetime.now().timestamp() * 1000)

    async def ensure_authenticated(self) -> None:
        """Ensure the connection is authenticated, login if necessary."""
        if self._authenticated:
            return

        async with self._auth_lock:
            if self._authenticated:
                return
            await self._login()

    async def _login(self) -> None:
        """Perform login authentication."""
        hashed_pwd = hashlib.md5(self._password.encode()).hexdigest()
        payload = {
            "login": {
                "pwd": hashed_pwd,
                "timestamp": self.get_timestamp()
            }
        }

        try:
            async with self.session.post(
                self.set_url, json=payload, timeout=self.timeout
            ) as response:
                raw_response = await response.text()
                data = json.loads(raw_response)

                if data.get("errcode") == "1":
                    raise AuthenticationError("Invalid credentials")

                self._authenticated = True
                _LOGGER.debug("Successfully authenticated to Twibi router at %s", self.host)

        except aiohttp.ClientError as err:
            raise ConnectionError("Failed to connect to router") from err
        except json.JSONDecodeError as err:
            raise APIError("Invalid response format from router") from err

    async def get_data(self, modules: list[str]) -> dict[str, Any]:
        """Fetch data from specified modules."""
        await self.ensure_authenticated()

        try:
            url = self.get_url + ",".join(modules)
            _LOGGER.debug("Fetching data from URL: %s", url)

            async with self.session.get(url, timeout=self.timeout) as response:
                raw_data = await response.text()
                _LOGGER.debug("Raw response: %s", raw_data[:500])  # Log first 500 chars

                if not raw_data.strip():
                    raise APIError("Empty response from router")

                try:
                    return json.loads(raw_data)
                except json.JSONDecodeError as json_err:
                    # Check if we got an HTML login page instead of JSON
                    if raw_data.strip().lower().startswith('<!doctype html') or '<html' in raw_data.lower():
                        _LOGGER.warning("Router returned HTML login page instead of JSON data")
                        # Reset authentication state
                        self._authenticated = False
                        raise AuthenticationError("Router session expired or authentication failed - got login page") from None

                    _LOGGER.error("JSON decode error. Raw response: %s", raw_data)
                    raise APIError(f"Invalid JSON response from router: {json_err}") from json_err

        except aiohttp.ClientError as err:
            # Reset authentication on connection errors
            self._authenticated = False
            raise ConnectionError(f"Failed to fetch data: {err}") from err

    async def send_command(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a command to the router."""
        await self.ensure_authenticated()

        try:
            async with self.session.post(
                self.set_url, json=payload, timeout=self.timeout
            ) as response:
                raw_response = await response.text()
                return json.loads(raw_response)

        except aiohttp.ClientError as err:
            # Reset authentication on connection errors
            self._authenticated = False
            raise ConnectionError(f"Failed to send command: {err}") from err
        except json.JSONDecodeError as err:
            raise APIError("Invalid JSON response from router") from err

    def invalidate_auth(self) -> None:
        """Invalidate current authentication state."""
        self._authenticated = False


class APIError(Exception):
    """Base API error."""


class AuthenticationError(APIError):
    """Authentication failed error."""


class ConnectionError(APIError):
    """Connection failed error."""
