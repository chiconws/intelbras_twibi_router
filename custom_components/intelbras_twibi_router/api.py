"""API module for interacting with Twibi Router."""

from datetime import datetime
import hashlib
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class TwibiAPI:
    """Twibi Router API class using async aiohttp."""

    def __init__(
        self, twibi_ip_address: str, password: str, exclude_wired: bool, update_interval: int, session: aiohttp.ClientSession
    ) -> None:
        """Initialize the Twibi Router API."""
        self.twibi_ip_address = twibi_ip_address
        self.password = password
        self.exclude_wired = exclude_wired
        self.update_interval = update_interval
        self.session = session

    async def login(self) -> bool:
        """Login to router."""
        hashed_pwd = hashlib.md5(self.password.encode()).hexdigest()
        timestamp = int(datetime.timestamp(datetime.now()) * 1000)
        payload = {"login": {"pwd": hashed_pwd, "timestamp": timestamp}}

        try:
            async with self.session.post(
                self.set_url,
                json=payload
            ) as response:
                raw_response = await response.text()
                data = json.loads(raw_response)

                if data.get("errcode") == "1":
                    raise AuthenticationError("Invalid credentials")

                return True
        except json.JSONDecodeError as err:
            _LOGGER.error(
                "Failed to parse login response: %s\nResponse: %s", err, raw_response
            )
            raise ConnectionError("Invalid response format from router") from err

    async def _get_module(self, module_id: str) -> Any:
        """Call API for each module."""
        while True:
            try:
                async with self.session.get(self.get_url + module_id) as response:

                    raw_response = await response.text()

                    return json.loads(raw_response)
            except json.JSONDecodeError:
                await self.login()

    async def get_online_list_including_wired(self) -> list:
        """Retrieve the list of online devices including wired connections."""
        data = await self._get_module("online_list")
        return data.get("online_list", []) if isinstance(data, dict) else data

    async def get_online_list_excluding_wired(self) -> list:
        """Retrieve the list of online devices excluding wired connections."""
        data = await self.get_online_list_including_wired()
        return [dev for dev in data if dev.get("wifi_mode") != "--"]

    async def get_online_list(self) -> callable:
        """Retrieve the list of online devices based on configuration."""
        if self.exclude_wired:
            return await self.get_online_list_excluding_wired()
        return await self.get_online_list_including_wired()

    async def get_wan_statistics(self) -> dict:
        """Get WAN statistics from the router."""
        data = await self._get_module("wan_statistic")
        return data.get("wan_statistic", [{}])[0]

    async def get_node_info(self) -> list:
        """Get node information about all Twibi devices."""
        data = await self._get_module("node_info")
        return data.get("node_info", [])

    @property
    def base_url(self) -> str:
        """Return base URL."""
        return f"http://{self.twibi_ip_address}/goform"

    @property
    def get_url(self) -> str:
        """Return get URL."""
        return f"{self.base_url}/get?module_id="

    @property
    def set_url(self) -> str:
        """Return set URL."""
        return f"{self.base_url}/set"


class AuthenticationError(Exception):
    """Authentication error."""
