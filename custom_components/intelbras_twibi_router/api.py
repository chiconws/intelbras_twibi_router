"""API module for interacting with Twibi Router."""
from datetime import datetime
import hashlib
import json
import logging

import aiohttp

from .const import DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

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

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp in milliseconds."""
        return int(datetime.now().timestamp() * 1000)

    async def login(self) -> bool:
        """Login to router."""
        hashed_pwd = hashlib.md5(self.password.encode()).hexdigest()
        payload = {"login": {"pwd": hashed_pwd, "timestamp": self.get_timestamp()}}

        try:
            async with self.session.post(
                self.set_url, json=payload, timeout=DEFAULT_TIMEOUT
            ) as response:
                raw_response = await response.text()
                data = json.loads(raw_response)

                if data["errcode"] == "1":
                    raise APIError("Invalid credentials")
                return True

        except aiohttp.ClientError as err:
            raise APIError("Connection failed") from err

        except json.JSONDecodeError as err:
            raise APIError("Invalid response format from router") from err

    async def get_modules(self, module_list: list[str]):
        """Retrieve module data from the router based on a list of module IDs."""
        try:
            async with self.session.get(
                self.get_url + ",".join(module_list), timeout=DEFAULT_TIMEOUT
            ) as response:
                data = await response.text()
                return json.loads(data)

        except aiohttp.ClientError as e:
            raise APIError(f"Client error: {e!s}") from e

        except json.JSONDecodeError as e:
            raise APIError("Invalid JSON response") from e

        except Exception as e:
            raise APIError(f"Unexpected error: {e!s}") from e

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
