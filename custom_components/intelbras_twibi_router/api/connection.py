"""Connection management for Twibi Router API."""

import asyncio
from collections.abc import Sequence
from datetime import datetime
import hashlib
import json
import logging
from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT
from .enums import RouterModule
from .models import AuthenticationResult, CommandResult

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

    async def authenticate(self) -> AuthenticationResult:
        """Authenticate with the router and return a typed result."""
        if self._authenticated:
            return AuthenticationResult(authenticated=True)

        async with self._auth_lock:
            if self._authenticated:
                return AuthenticationResult(authenticated=True)
            return await self._login()

    async def ensure_authenticated(self) -> None:
        """Ensure the connection is authenticated, login if necessary."""
        result = await self.authenticate()
        if not result.authenticated:
            raise AuthenticationError("Invalid credentials")

    async def _login(self) -> AuthenticationResult:
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
                data = self._decode_json_response(raw_response, reset_auth_on_html=True)
                result = AuthenticationResult.from_response(data)
                if not result.authenticated:
                    self._authenticated = False
                    return result

                self._authenticated = True
                _LOGGER.debug("Successfully authenticated to Twibi router at %s", self.host)
                return result

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            self._authenticated = False
            raise ConnectionError("Failed to connect to router") from err

    async def get_data(
        self,
        modules: Sequence[str | RouterModule],
    ) -> dict[str, Any]:
        """Fetch data from specified modules."""
        await self.ensure_authenticated()

        try:
            url = self.get_url + ",".join(str(module) for module in modules)
            _LOGGER.debug("Fetching data from URL: %s", url)

            async with self.session.get(url, timeout=self.timeout) as response:
                raw_data = await response.text()
                _LOGGER.debug("Raw response: %s", raw_data[:500])  # Log first 500 chars

                if not raw_data.strip():
                    raise APIError("Empty response from router")

                return self._decode_json_response(raw_data, reset_auth_on_html=True)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            # Reset authentication on connection errors
            self._authenticated = False
            raise ConnectionError(f"Failed to fetch data: {err}") from err

    async def send_command(self, payload: dict[str, Any]) -> CommandResult:
        """Send a command to the router."""
        await self.ensure_authenticated()
        command = next(iter(payload), "unknown")

        try:
            async with self.session.post(
                self.set_url, json=payload, timeout=self.timeout
            ) as response:
                raw_response = await response.text()
                data = self._decode_json_response(raw_response, reset_auth_on_html=True)
                return CommandResult.from_response(command, data)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            # Reset authentication on connection errors
            self._authenticated = False
            raise ConnectionError(f"Failed to send command: {err}") from err

    def invalidate_auth(self) -> None:
        """Invalidate current authentication state."""
        self._authenticated = False

    def _decode_json_response(
        self,
        raw_response: str,
        *,
        reset_auth_on_html: bool,
    ) -> dict[str, Any]:
        """Decode a router response and handle HTML auth redirects."""
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as err:
            if (
                raw_response.strip().lower().startswith("<!doctype html")
                or "<html" in raw_response.lower()
            ):
                if reset_auth_on_html:
                    self._authenticated = False
                raise AuthenticationError(
                    "Router session expired or authentication failed - got login page"
                ) from None

            _LOGGER.error("JSON decode error. Raw response: %s", raw_response)
            raise APIError(f"Invalid JSON response from router: {err}") from err


class APIError(Exception):
    """Base API error."""


class AuthenticationError(APIError):
    """Authentication failed error."""


class ConnectionError(APIError):
    """Connection failed error."""
