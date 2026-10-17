"""Constants for the Intelbras Twibi integration."""

from datetime import timedelta

DOMAIN = "intelbras_twibi"
MANUFACTURER = "Intelbras"

DEFAULT_HOST = "192.168.5.1"
SCAN_INTERVAL = timedelta(seconds=30)

CONF_WIFI_ONLY = "wifi_only"
CONF_TRACKED_DEVICES = "tracked_devices"
