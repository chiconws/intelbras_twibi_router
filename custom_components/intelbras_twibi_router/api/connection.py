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
        self._auth_cookie_name: str | None = None
        self._auth_cookie_value: str | None = None
        self._firmware_version: str | None = None
        self._use_cookie_auth = False

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
                self._update_auth_cookie(response)
                raw_response = await response.text()
                data = self._decode_json_response(raw_response, reset_auth_on_html=True)
                result = AuthenticationResult.from_response(data)
                if not result.authenticated:
                    self.invalidate_auth()
                    return result

                self._authenticated = True
                _LOGGER.debug("Successfully authenticated to Twibi router at %s", self.host)
                return result

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            self.invalidate_auth()
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
            return await self._request_json("GET", url)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            self.invalidate_auth()
            raise ConnectionError(f"Failed to fetch data: {err}") from err

    async def send_command(self, payload: dict[str, Any]) -> CommandResult:
        """Send a command to the router."""
        await self.ensure_authenticated()
        command = next(iter(payload), "unknown")

        try:
            data = await self._request_json(
                "POST",
                self.set_url,
                json_payload=payload,
            )
            return CommandResult.from_response(command, data)

        except (asyncio.TimeoutError, aiohttp.ClientError) as err:
            self.invalidate_auth()
            raise ConnectionError(f"Failed to send command: {err}") from err

    def invalidate_auth(self) -> None:
        """Invalidate current authentication state."""
        self._authenticated = False
        self._auth_cookie_name = None
        self._auth_cookie_value = None

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
                    self.invalidate_auth()
                raise AuthenticationError(
                    "Router session expired or authentication failed - got login page"
                ) from None

            _LOGGER.error("JSON decode error. Raw response: %s", raw_response)
            raise APIError(f"Invalid JSON response from router: {err}") from err

    def _request_headers(self) -> dict[str, str] | None:
        """Build headers for authenticated Twibi API requests."""
        if not self._use_cookie_auth:
            return None

        if not self._auth_cookie_name or not self._auth_cookie_value:
            return None

        return {
            "Cookie": f"{self._auth_cookie_name}={self._auth_cookie_value}",
        }

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON request with firmware-aware auth compatibility handling."""
        allow_cookie_retry = bool(
            self._auth_cookie_name and self._auth_cookie_value and not self._use_cookie_auth
        )

        for attempt in range(2):
            use_cookie_headers = self._use_cookie_auth or attempt == 1
            async with self.session.request(
                method,
                url,
                json=json_payload,
                headers=self._request_headers() if use_cookie_headers else None,
                timeout=self.timeout,
            ) as response:
                self._update_auth_cookie(response)
                raw_response = await response.text()
                _LOGGER.debug("Raw response: %s", raw_response[:500])

                if not raw_response.strip():
                    raise APIError("Empty response from router")

                try:
                    data = self._decode_json_response(
                        raw_response,
                        reset_auth_on_html=not allow_cookie_retry or use_cookie_headers,
                    )
                except AuthenticationError:
                    if allow_cookie_retry and not use_cookie_headers:
                        self._use_cookie_auth = True
                        _LOGGER.debug(
                            "Retrying %s request with cookie auth compatibility for %s",
                            method,
                            self.host,
                        )
                        continue
                    self.invalidate_auth()
                    raise

                self._update_firmware_profile(data)
                return data

        raise APIError(f"Unable to decode router response for {method} {url}")

    def _update_auth_cookie(self, response: aiohttp.ClientResponse) -> None:
        """Persist the router session cookie even when the client jar rejects it."""
        preferred_cookie_names = ("MESH_user",)

        for cookie_name in preferred_cookie_names:
            if cookie_name in response.cookies:
                self._store_auth_cookie(cookie_name, response.cookies[cookie_name].value)
                return

        for cookie_name, cookie in response.cookies.items():
            self._store_auth_cookie(cookie_name, cookie.value)
            return

    def _store_auth_cookie(self, cookie_name: str, cookie_value: str) -> None:
        """Store the current router session cookie."""
        if not cookie_name or not cookie_value:
            return

        self._auth_cookie_name = cookie_name
        self._auth_cookie_value = cookie_value
        if cookie_name == "MESH_user" and self._firmware_version is None:
            self._use_cookie_auth = True

    def _update_firmware_profile(self, data: dict[str, Any]) -> None:
        """Update firmware-aware compatibility settings from a router payload."""
        firmware_version = self._extract_firmware_version(data)
        if not firmware_version:
            return

        previous_version = self._firmware_version
        self._firmware_version = firmware_version
        should_use_cookie_auth = self._firmware_uses_cookie_auth(firmware_version)

        if should_use_cookie_auth and not self._use_cookie_auth:
            self._use_cookie_auth = True
            _LOGGER.debug(
                "Enabled Twibi cookie auth compatibility for firmware %s on %s",
                firmware_version,
                self.host,
            )
        elif not should_use_cookie_auth and self._use_cookie_auth:
            self._use_cookie_auth = False
            _LOGGER.debug(
                "Restored legacy Twibi auth mode for firmware %s on %s",
                firmware_version,
                self.host,
            )
        elif previous_version != firmware_version:
            _LOGGER.debug(
                "Detected Twibi firmware %s on %s",
                firmware_version,
                self.host,
            )

    def _extract_firmware_version(self, data: dict[str, Any]) -> str | None:
        """Extract the current firmware version from a router payload."""
        version_info = data.get(RouterModule.GET_VERSION)
        if isinstance(version_info, dict):
            current_version = version_info.get("current_version")
            if current_version:
                return str(current_version).strip()

        node_info = data.get(RouterModule.NODE_INFO)
        if isinstance(node_info, list):
            primary_node = next(
                (
                    node
                    for node in node_info
                    if isinstance(node, dict) and str(node.get("role")) == "1"
                ),
                None,
            )
            version_node = primary_node or next(
                (node for node in node_info if isinstance(node, dict)),
                None,
            )
            if version_node and version_node.get("dut_version"):
                return str(version_node["dut_version"]).strip()

        return None

    @staticmethod
    def _firmware_uses_cookie_auth(version: str) -> bool:
        """Return whether a firmware version should use cookie-auth compatibility."""
        numeric_parts: list[int] = []
        for part in version.lstrip("vV").split("."):
            if not part.isdigit():
                return False
            numeric_parts.append(int(part))

        return tuple(numeric_parts) >= (1, 1, 11)


class APIError(Exception):
    """Base API error."""


class AuthenticationError(APIError):
    """Authentication failed error."""


class ConnectionError(APIError):
    """Connection failed error."""
