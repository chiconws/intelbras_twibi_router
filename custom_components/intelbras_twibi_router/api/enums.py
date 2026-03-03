"""Enum types and protocol constants for the Twibi API."""

from enum import StrEnum


class AuthenticationErrorCode(StrEnum):
    """Known authentication error codes returned by the Twibi API."""

    INVALID_CREDENTIALS = "1"


class CommandErrorCode(StrEnum):
    """Known command result codes returned by the Twibi API."""

    SUCCESS = "0"


class NodeRole(StrEnum):
    """Known roles returned by the Twibi node API."""

    SECONDARY = "0"
    PRIMARY = "1"


class NodeLedState(StrEnum):
    """Known LED states returned by the Twibi node API."""

    OFF = "0"
    ON = "1"


class GuestNetworkState(StrEnum):
    """Known guest network states returned by the Twibi API."""

    DISABLED = "0"
    ENABLED = "1"


class UpnpState(StrEnum):
    """Known UPnP states returned by the Twibi API."""

    DISABLED = "0"
    ENABLED = "1"


class DhcpState(StrEnum):
    """Known DHCP states returned by the Twibi API."""

    DISABLED = "0"
    ENABLED = "1"


class FirmwareUpdateState(StrEnum):
    """Known firmware update availability states returned by the Twibi API."""

    NO_UPDATE = "0"
    UPDATE_AVAILABLE = "1"


class NodeNetworkStatus(StrEnum):
    """Known connectivity states returned by the primary node."""

    DISCONNECTED = "0"
    CONNECTED = "1"


class NetworkLinkState(StrEnum):
    """Known values returned by the net_link_status module."""

    CONNECTED = "3"


class GuestNetworkBandwidthLimit(StrEnum):
    """Known guest network bandwidth limit markers returned by the Twibi API."""

    UNLIMITED = "0"


class GuestNetworkTimeRestriction(StrEnum):
    """Known guest network schedule values used by the Twibi API."""

    ALWAYS = "always"


class RouterConnectionState(StrEnum):
    """States exposed by the network status sensor."""

    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    UNKNOWN = "Unknown"


class DeviceConnectionType(StrEnum):
    """Human-readable connection types exposed for connected clients."""

    ETHERNET = "Ethernet"
    FIVE_GHZ = "5GHz"
    TWO_FOUR_GHZ = "2.4GHz"
    UNKNOWN = "Unknown"


class DeviceRssiDefault(StrEnum):
    """Default RSSI placeholder used by the Twibi API."""

    UNKNOWN = "0"


class DeviceTxRateDefault(StrEnum):
    """Default TX rate placeholder used by the Twibi API."""

    UNKNOWN = "0"


class WifiMode(StrEnum):
    """Known Wi-Fi mode values returned for connected devices."""

    WIRED = "--"
    FIVE_GHZ = "AC"
    TWO_FOUR_GHZ = "BGN"

    @property
    def connection_type(self) -> DeviceConnectionType:
        """Return the human-readable connection type for this Wi-Fi mode."""
        match self:
            case WifiMode.WIRED:
                return DeviceConnectionType.ETHERNET
            case WifiMode.FIVE_GHZ:
                return DeviceConnectionType.FIVE_GHZ
            case WifiMode.TWO_FOUR_GHZ:
                return DeviceConnectionType.TWO_FOUR_GHZ
        return DeviceConnectionType.UNKNOWN


class WifiSecurityType(StrEnum):
    """Known Wi-Fi security type values used by the Twibi API."""

    AES = "aes"


class WifiSecurityMode(StrEnum):
    """Known Wi-Fi security mode values used by the Twibi API."""

    PSK_PSK2 = "psk psk2"
