"""Constants for the Twibi Router integration."""
import aiohttp

DOMAIN = 'intelbras_twibi_router'

CONF_TWIBI_IP_ADDRESS = 'Endereço IP do Twibi'
CONF_PASSWORD = 'password'
CONF_UPDATE_INTERVAL = 'Intervalo de atualização (em segundos)'
CONF_EXCLUDE_WIRED = "Apenas dispositivos conectados ao Wi-Fi"

DEFAULT_TWIBI_IP_ADDRESS = '192.168.5.1'
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_EXCLUDE_WIRED = True
DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=5)

MANUFACTURER = "Intelbras"
