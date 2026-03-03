"""Constants for the Twibi Router integration."""

import aiohttp
import voluptuous as vol

DOMAIN = "intelbras_twibi_router"

CONF_TWIBI_IP_ADDRESS = "Endereço IP do Twibi"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "Intervalo de atualização (em segundos)"
CONF_EXCLUDE_WIRED = "Apenas dispositivos conectados ao Wi-Fi"
CONF_SELECTED_DEVICES = "Dispositivos selecionados"
CONF_TRACK_ALL_DEVICES = "_track_all_devices"

DEFAULT_TWIBI_IP_ADDRESS = "192.168.5.1"
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_EXCLUDE_WIRED = True
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=5)

MANUFACTURER = "Intelbras"

MODULES = ["node_info", "online_list", "wan_statistic"]


NODE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("ip"): str,
        vol.Required("role"): vol.In(["0", "1"]),
        vol.Required("netmask"): str,
        vol.Required("gw"): str,
        vol.Required("first_dns"): str,
        vol.Required("sec_dns"): str,
        vol.Required("up_speed"): str,
        vol.Required("down_speed"): str,
        vol.Required("serial_number"): str,
        vol.Required("led"): vol.In(["0", "1"]),
        vol.Required("location"): str,
        vol.Required("lan_mac"): str,
        vol.Required("wan_mac"): str,
        vol.Required("5Gwifi_mac"): str,
        vol.Required("2Gwifi_mac"): str,
        vol.Required("dut_name"): str,
        vol.Required("dut_version"): str,
        vol.Required("sn"): str,
        vol.Required("groupsn"): str,
        vol.Required("Uptime"): str,
        vol.Required("up_date"): str,
        vol.Required("ipv6"): str,
        vol.Required("net_status"): vol.In(["0", "1"]),
        vol.Required("link_status"): str,
        vol.Optional("link_quality"): vol.Any(str, type(None)),
    }
)

ONLINE_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required("dev_ip"): str,
        vol.Required("dev_name"): str,
        vol.Required("dev_mac"): str,
        vol.Required("download_speed"): str,
        vol.Required("upload_speed"): str,
        vol.Required("connect_time"): str,
        vol.Required("sn"): str,
        vol.Optional("link_type"): vol.Any(str, type(None)),
        vol.Required("rssi"): str,
        vol.Required("tx_rate"): str,
        vol.Required("wifi_mode"): vol.In(["--", "AC", "BGN"]),
    }
)

WAN_STATISTIC_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("up_speed"): str,
        vol.Required("down_speed"): str,
        vol.Required("ttotal_up"): str,
        vol.Required("ttotal_down"): str,
    }
)

LAN_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("lan_ip"): str,
        vol.Required("lan_mask"): str,
        vol.Required("dhcp_en"): vol.In(["0", "1"]),
        vol.Required("start_ip"): str,
        vol.Required("end_ip"): str,
        vol.Required("lease_time"): str,
        vol.Required("dns1"): str,
        vol.Required("dns2"): str,
    }
)

WAN_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("id"): str,
        vol.Required("ip"): str,
        vol.Required("netmask"): str,
        vol.Required("gw"): str,
        vol.Required("mac"): str,
        vol.Required("first_dns"): str,
        vol.Required("sec_dns"): str,
        vol.Required("ipv6"): str,
        vol.Required("ipv6_gw"): str,
        vol.Required("ipv6_first_dns"): str,
        vol.Required("ipv6_sec_dns"): str,
    }
)

WIFI_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("ssid"): str,
        vol.Required("type"): str,
        vol.Required("security"): str,
        vol.Required("pass"): str,
    }
)

GUEST_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("guest_en"): vol.In(["0", "1"]),
        vol.Required("guest_ssid"): str,
        vol.Required("guest_pass"): str,
        vol.Required("guest_time"): str,
        vol.Required("limit"): str,
    }
)

VERSION_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("hasNew"): vol.In(["0", "1"]),
        vol.Required("version"): str,
        vol.Required("changelog"): str,
        vol.Required("current_version"): str,
        vol.Required("sysHasNew"): vol.In(["0", "1"]),
    }
)

UPNP_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("upnp_en"): vol.In(["0", "1"]),
    }
)

NET_LINK_STATUS_SCHEMA = vol.Schema(
    {
        vol.Required("net_status"): vol.In(["3"]),
        vol.Required("id"): str,
    }
)

MAIN_SCHEMA = vol.Schema(
    {
        vol.Required("node_info"): vol.All([NODE_SCHEMA], vol.Length(min=1)),
        vol.Required("online_list"): [ONLINE_DEVICE_SCHEMA],
        vol.Required("wan_statistic"): [WAN_STATISTIC_SCHEMA],
        vol.Optional("wan_info"): vol.Any([WAN_INFO_SCHEMA], type(None)),
        vol.Optional("lan_info"): vol.Any(LAN_INFO_SCHEMA, type(None)),
        vol.Optional("wifi"): vol.Any(WIFI_INFO_SCHEMA, type(None)),
        vol.Optional("guest_info"): vol.Any(GUEST_INFO_SCHEMA, type(None)),
        vol.Optional("getversion"): vol.Any(VERSION_INFO_SCHEMA, type(None)),
        vol.Optional("upnp_info"): vol.Any(UPNP_INFO_SCHEMA, type(None)),
        vol.Optional("remote_web"): vol.Any(dict, type(None)),
        vol.Optional("static_ip"): vol.Any(list, type(None)),
        vol.Optional("net_link_status"): vol.Any([NET_LINK_STATUS_SCHEMA], type(None)),
        vol.Optional("link_module"): vol.Any(list, type(None)),
        vol.Optional("port_list"): vol.Any(dict, type(None)),
        vol.Optional("dns_conf"): vol.Any(dict, type(None)),
        vol.Optional("tr069_info"): vol.Any(dict, type(None)),
        vol.Optional("mac_clone"): vol.Any(list, type(None)),
    },
    extra=vol.ALLOW_EXTRA,  # Allow any additional fields from the API
)
