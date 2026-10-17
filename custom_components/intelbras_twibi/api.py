"""Async client for the Intelbras Twibi local HTTP API. No Home Assistant imports."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)
CORE_MODULES = ("node_info", "online_list", "wan_statistic")
# Fetched one per request: some firmwares drop the whole reply when a module is missing.
OPTIONAL_MODULES = ("wan_info", "guest_info", "upnp_info")
OPTIONAL_MODULE_DELAY = 0.1
SESSION_COOKIE = "MESH_user"
# Firmware 1.1.11+ only accepts the session cookie as an explicit header.
COOKIE_AUTH_FIRMWARE = (1, 1, 11)


class TwibiError(Exception):
    """The router returned something unusable."""


class TwibiConnectionError(TwibiError):
    """The router could not be reached."""


class TwibiAuthError(TwibiError):
    """The router rejected the password."""


@dataclass(frozen=True, slots=True)
class Node:
    """One mesh unit."""

    serial: str
    model: str
    firmware: str
    ip: str
    mac: str
    is_primary: bool
    led_on: bool
    uptime: int | None
    wan_connected: bool
    link_quality: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Node:
        """Parse a node_info entry."""
        is_primary = str(data.get("role")) == "1"
        return cls(
            serial=data["sn"],
            model=data.get("dut_name") or "Twibi",
            firmware=data.get("dut_version", ""),
            ip=data.get("ip", ""),
            mac=data.get("lan_mac", ""),
            is_primary=is_primary,
            led_on=str(data.get("led")) == "1",
            uptime=_int(data.get("Uptime")),
            wan_connected=str(data.get("net_status")) == "1",
            link_quality=_backhaul_dbm(data.get("link_quality")) if not is_primary else None,
        )


@dataclass(frozen=True, slots=True)
class Client:
    """A device connected to the mesh."""

    mac: str
    name: str
    ip: str
    band: str  # "wired", "2.4ghz" or "5ghz"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Client:
        """Parse an online_list entry."""
        band = {"--": "wired", "AC": "5ghz", "BGN": "2.4ghz"}.get(data.get("wifi_mode", ""), "wired")
        return cls(
            mac=data["dev_mac"].upper(),
            name=data.get("dev_name") or "",
            ip=data.get("dev_ip", ""),
            band=band,
        )


@dataclass(frozen=True, slots=True)
class GuestNetwork:
    """Guest Wi-Fi settings, kept whole so toggling preserves them."""

    enabled: bool
    ssid: str
    password: str
    time: str
    limit: str


@dataclass(slots=True)
class RouterData:
    """One poll of the router."""

    nodes: list[Node]
    clients: dict[str, Client]
    wan_download: float | None = None
    wan_upload: float | None = None
    wan_ip: str | None = None
    guest: GuestNetwork | None = None
    upnp_enabled: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def primary(self) -> Node:
        """Return the node that holds the WAN link."""
        return next((n for n in self.nodes if n.is_primary), self.nodes[0])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RouterData:
        """Build a snapshot from merged module replies."""
        nodes = [Node.from_dict(n) for n in data.get("node_info") or []]
        if not nodes:
            raise TwibiError("Router returned no mesh nodes")
        clients = [Client.from_dict(c) for c in data.get("online_list") or []]
        wan = (data.get("wan_statistic") or [{}])[0]
        wan_info = (data.get("wan_info") or [{}])[0]
        guest = data.get("guest_info")
        upnp = data.get("upnp_info")
        return cls(
            nodes=nodes,
            clients={c.mac: c for c in clients},
            wan_download=_float(wan.get("down_speed")),
            wan_upload=_float(wan.get("up_speed")),
            wan_ip=wan_info.get("ip") or None,
            guest=GuestNetwork(
                enabled=str(guest.get("guest_en")) == "1",
                ssid=guest.get("guest_ssid", ""),
                password=guest.get("guest_pass", ""),
                time=guest.get("guest_time") or "always",
                limit=guest.get("limit") or "0",
            )
            if guest
            else None,
            upnp_enabled=str(upnp.get("upnp_en")) == "1" if upnp else None,
            raw=data,
        )


class TwibiClient:
    """Talks to /goform on the primary node."""

    def __init__(self, host: str, password: str, session: aiohttp.ClientSession) -> None:
        """Store connection details; nothing is sent until the first call."""
        self.host = host
        self._password = password
        self._session = session
        self._logged_in = False
        self._cookie: str | None = None
        self._cookie_auth = False
        self._lock = asyncio.Lock()

    @property
    def _url(self) -> str:
        return f"http://{self.host}/goform"

    async def async_login(self) -> None:
        """Log in; raises TwibiAuthError on a wrong password."""
        payload = {
            "login": {
                "pwd": hashlib.md5(self._password.encode()).hexdigest(),
                "timestamp": _now_ms(),
            }
        }
        data = await self._send("POST", f"{self._url}/set", payload, login=True)
        if str(data.get("errcode")) == "1":
            raise TwibiAuthError("Invalid password")
        self._logged_in = True

    async def async_get_data(self) -> RouterData:
        """Fetch everything the integration shows."""
        data = await self._get(CORE_MODULES)
        if not data.get("node_info"):
            raise TwibiError("Router returned no mesh nodes")
        for module in OPTIONAL_MODULES:
            try:
                data.update(await self._get((module,)))
            except TwibiAuthError:
                raise
            except TwibiError as err:
                _LOGGER.debug("Skipping optional module %s: %s", module, err)
            await asyncio.sleep(OPTIONAL_MODULE_DELAY)
        snapshot = RouterData.from_dict(data)
        if version := _version(snapshot.primary.firmware):
            self._cookie_auth = version >= COOKIE_AUTH_FIRMWARE
        return snapshot

    async def async_set_led(self, serial: str, on: bool) -> None:
        """Turn a node's status LED on or off."""
        await self._command("led", {"led_en": "1" if on else "0", "sn": serial})

    async def async_set_upnp(self, on: bool) -> None:
        """Enable or disable UPnP."""
        await self._command("upnp_info", {"upnp_en": "1" if on else "0"})

    async def async_set_guest(self, guest: GuestNetwork, on: bool) -> None:
        """Enable or disable the guest network, keeping its other settings."""
        await self._command(
            "guest_info",
            {
                "guest_en": "1" if on else "0",
                "guest_ssid": guest.ssid,
                "guest_pass": guest.password,
                "guest_time": guest.time,
                "limit": guest.limit,
            },
        )

    async def async_reboot(self) -> None:
        """Reboot the whole mesh."""
        await self._command("sys_reboot", {"action": "reboot"})

    async def _get(self, modules: tuple[str, ...]) -> dict[str, Any]:
        return await self._authed("GET", f"{self._url}/get?module_id={','.join(modules)}")

    async def _command(self, name: str, values: dict[str, Any]) -> None:
        payload = {name: {**values, "timestamp": str(_now_ms())}}
        data = await self._authed("POST", f"{self._url}/set", payload)
        if str(data.get("errcode", "0")) != "0":
            raise TwibiError(f"Router rejected {name} (errcode {data.get('errcode')})")

    async def _authed(self, method: str, url: str, payload: dict | None = None) -> dict[str, Any]:
        """Send a request, logging in first and once more if the session expired."""
        for attempt in range(2):
            async with self._lock:
                if not self._logged_in:
                    await self.async_login()
            try:
                return await self._send(method, url, payload)
            except _SessionExpired:
                self._logged_in = False
                if attempt == 0 and self._cookie and not self._cookie_auth:
                    self._cookie_auth = True  # newer firmware: retry with the cookie header
        raise TwibiError("Router keeps returning the login page")

    async def _send(
        self, method: str, url: str, payload: dict | None, *, login: bool = False
    ) -> dict[str, Any]:
        headers = {"Cookie": self._cookie} if self._cookie and self._cookie_auth and not login else None
        try:
            async with self._session.request(
                method, url, json=payload, headers=headers, timeout=TIMEOUT
            ) as resp:
                self._store_cookie(resp)
                text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            self._logged_in = False
            raise TwibiConnectionError(f"Cannot reach {self.host}: {err}") from err
        if not text.strip():
            raise TwibiError("Empty reply from router")
        if "<html" in text[:200].lower() or text.lstrip().lower().startswith("<!doctype"):
            raise _SessionExpired
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise TwibiError(f"Invalid JSON from router: {text[:100]!r}") from err

    def _store_cookie(self, resp: aiohttp.ClientResponse) -> None:
        # HA's shared session rejects cookies from IP hosts, so keep it ourselves.
        name = SESSION_COOKIE if SESSION_COOKIE in resp.cookies else next(iter(resp.cookies), None)
        if name and (value := resp.cookies[name].value):
            self._cookie = f"{name}={value}"
            self._cookie_auth = self._cookie_auth or name == SESSION_COOKIE


class _SessionExpired(TwibiError):
    """The router answered with its HTML login page."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _backhaul_dbm(value: Any) -> int | None:
    # Wi-Fi backhaul reports dBm (-82); a cabled backhaul reports "1", which is no signal.
    dbm = _int(value)
    return dbm if dbm is not None and dbm < 0 else None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _version(text: str) -> tuple[int, ...]:
    parts = text.lstrip("vV").split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else ()
