"""Constants for the Twibi API layer."""

import aiohttp

from .enums import RouterModule

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=5)
OPTIONAL_MODULE_REQUEST_DELAY_SECONDS = 0.1

DEFAULT_ROUTER_DATA_MODULES: tuple[RouterModule, ...] = (
    RouterModule.NODE_INFO,
    RouterModule.ONLINE_LIST,
    RouterModule.WAN_STATISTIC,
)

OPTIONAL_ROUTER_DATA_MODULES: tuple[RouterModule, ...] = (
    RouterModule.WAN_INFO,
    RouterModule.LAN_INFO,
    RouterModule.WIFI,
    RouterModule.GUEST_INFO,
    RouterModule.UPNP_INFO,
)

AVAILABLE_ROUTER_MODULES: tuple[RouterModule, ...] = (
    *DEFAULT_ROUTER_DATA_MODULES,
    *OPTIONAL_ROUTER_DATA_MODULES,
    RouterModule.STATIC_IP,
    RouterModule.PORT_LIST,
    RouterModule.TR069_INFO,
    RouterModule.REMOTE_WEB,
    RouterModule.DNS_CONF,
    RouterModule.MAC_CLONE,
    RouterModule.GET_VERSION,
    RouterModule.NET_LINK_STATUS,
    RouterModule.LINK_MODULE,
)
