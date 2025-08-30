"""Constants for the Twibi Router integration."""

import aiohttp
import voluptuous as vol

DOMAIN = "intelbras_twibi_router"

CONF_TWIBI_IP_ADDRESS = "Endereço IP do Twibi"
CONF_PASSWORD = "password"
CONF_UPDATE_INTERVAL = "Intervalo de atualização (em segundos)"
CONF_EXCLUDE_WIRED = "Apenas dispositivos conectados ao Wi-Fi"
CONF_SELECTED_DEVICES = "Dispositivos selecionados"

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
        vol.Required("net_status"): str,
        vol.Required("link_status"): str,
        vol.Optional("link_quality"): str,
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
        vol.Optional("link_type"): str,
        vol.Required("rssi"): str,
        vol.Required("tx_rate"): str,
        vol.Required("wifi_mode"): str,
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

MAIN_SCHEMA = vol.Schema(
    {
        vol.Required("node_info"): vol.All([NODE_SCHEMA], vol.Length(min=1)),
        vol.Required("online_list"): [ONLINE_DEVICE_SCHEMA],
        vol.Required("wan_statistic"): [WAN_STATISTIC_SCHEMA],
    }
)
