"""API module for interacting with Twibi Router."""
import hashlib
import json
from typing import Any

import aiohttp

from .const import DEFAULT_TIMEOUT
from .utils import get_timestamp

class TwibiAPI:
    """Twibi Router API class using async aiohttp."""

    def __init__(
        self,
        twibi_ip_address: str,
        password: str,
        exclude_wired: bool,
        update_interval: int,
        session: aiohttp.ClientSession,
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
        payload = {"login": {"pwd": hashed_pwd, "timestamp": get_timestamp()}}

        try:
            async with self.session.post(
                self.set_url, json=payload, timeout=DEFAULT_TIMEOUT
            ) as response:
                raw_response = await response.text()
                data = json.loads(raw_response)

                if data.get("errcode") == "1":
                    raise APIError("Invalid credentials")
                return True

        except aiohttp.ClientError as e:
            raise APIError("Connection failed") from e

        except json.JSONDecodeError as err:
            raise ConnectionError("Invalid response format from router") from err

    async def _get_module(self, module_id: str) -> Any:
        """Call API for each module."""
        try:
            async with self.session.get(
                self.get_url + module_id, timeout=DEFAULT_TIMEOUT
            ) as response:
                raw_response = await response.text()
                return json.loads(raw_response)

        except aiohttp.ClientError as e:
            raise APIError(f"Client error: {e!s}") from e

        except json.JSONDecodeError as e:
            raise APIError("Invalid JSON response") from e

    async def _get_online_list_including_wired(self) -> list:
        """Retrieve the list of online devices including wired connections."""
        data = await self._get_module("online_list")
        return data.get("online_list", []) if isinstance(data, dict) else data

    async def _get_online_list_excluding_wired(self) -> list:
        """Retrieve the list of online devices excluding wired connections."""
        data = await self._get_online_list_including_wired()
        return [dev for dev in data if dev.get("wifi_mode") != "--"]

    async def get_online_list(self) -> list:
        """Retrieve the list of online devices based on configuration."""
        if self.exclude_wired:
            return await self._get_online_list_excluding_wired()
        return await self._get_online_list_including_wired()

    async def get_wan_statistics(self) -> dict:
        """Get WAN statistics from the router."""
        data = await self._get_module("wan_statistic")
        return data.get("wan_statistic", [{}])[0]

    async def get_node_info(self) -> list:
        """Get node information about all Twibi devices."""
        data = await self._get_module("node_info")

        return sorted(
            data.get("node_info", []),
            key=lambda n: 0 if n.get("role") == "1" else 1
        )

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

class APIError(aiohttp.ClientError):
    """Generic API error."""
