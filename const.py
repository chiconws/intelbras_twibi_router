"""Constants for the Twibi Router integration."""

DOMAIN = 'intelbras_twibi_router'

CONF_TWIBI_IP_ADDRESS = 'Endereço IP do Twibi'
CONF_PASSWORD = 'password'
CONF_UPDATE_INTERVAL = 'Intervalo de atualização (em segundos)'
CONF_EXCLUDE_WIRED = "Apenas dispositivos conectados ao Wi-Fi"

GET_MODULES = [
    'online_list',
    'net_link_status',
    'lan_info',
    'link_module',
    'localhost',
    'getversion',
    'getupgradestatus',
    'guest_info',
    'port_list',
    'serach_node',
    'static_ip',
    'static_wan_info',
    'dynamic_wan_info',
    'mac_clone',
    'dns_conf',
    'elink',
    'upnp_info',
    'tr069_info',
    'remote_web',
    'net_link_check',
    'node_info',
    'wan_info',
    'wan_statistic',
    'wifi',
]
