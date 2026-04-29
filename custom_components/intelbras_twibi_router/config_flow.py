"""Config flow for Twibi Router integration."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APIError, AuthenticationError
from .api.models import OnlineDevice
from .twibi_api import TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    CONF_TRACK_ALL_DEVICES,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_EXCLUDE_WIRED,
    DEFAULT_TWIBI_IP_ADDRESS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _device_option_label(device: OnlineDevice | dict) -> str:
    """Build a user-facing label for a device selection option."""
    if isinstance(device, OnlineDevice):
        device_name = device.display_name
        device_ip = device.ip or "offline"
        connection = device.connection_type or "Unavailable"
    else:
        device_name = device.get("dev_name") or f"Device {device['dev_mac']}"
        device_ip = device.get("dev_ip") or "offline"
        connection = device.get("connection") or "Unavailable"

    return f"{device_name} ({device_ip}, {connection})"


def _device_select_selector(options: dict[str, str]) -> selector.SelectSelector:
    """Build a device selector that renders as a multi-select dropdown."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": mac, "label": label}
                for mac, label in options.items()
            ],
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _device_matches_mac(device_entry, mac: str) -> bool:
    """Return whether a device registry entry belongs to the given client MAC."""
    return (
        (DOMAIN, mac) in device_entry.identifiers
        or (dr.CONNECTION_NETWORK_MAC, mac) in device_entry.connections
    )


@callback
def _remove_deselected_trackers(
    hass,
    config_entry_id: str,
    selected_macs: set[str],
    track_all_devices: bool,
) -> None:
    """Remove device tracker entities that are no longer selected."""
    if track_all_devices:
        return

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    removed_macs: set[str] = set()

    for entity_entry in er.async_entries_for_config_entry(entity_registry, config_entry_id):
        if (
            entity_entry.platform == DOMAIN
            and entity_entry.domain == "device_tracker"
            and entity_entry.unique_id
            and entity_entry.unique_id not in selected_macs
        ):
            removed_macs.add(entity_entry.unique_id)
            entity_registry.async_remove(entity_entry.entity_id)

    if not removed_macs:
        return

    for device_entry in dr.async_entries_for_config_entry(device_registry, config_entry_id):
        if any(_device_matches_mac(device_entry, mac) for mac in removed_macs):
            device_registry.async_remove_device(device_entry.id)


class TwibiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twibi Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data = {}
        self._devices: list[OnlineDevice] = []
        self._api = None

    async def _async_authenticate_data(
        self,
        data: dict,
    ) -> str | None:
        """Validate router credentials for a data payload."""
        session = async_get_clientsession(self.hass)

        try:
            self._api = TwibiAPI(
                data[CONF_TWIBI_IP_ADDRESS],
                data[CONF_PASSWORD],
                data.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED),
                data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                session,
            )

            auth_result = await self._api.authenticate()
            if not auth_result.authenticated:
                return "Senha inválida."

        except APIError as err:
            _LOGGER.error("API Error during login: %s", err)
            return "Endereço IP ou senha inválidos."
        except Exception as err:
            _LOGGER.error("Unexpected error during login: %s", err)
            return "Erro inesperado. Verifique os logs."

        return None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            errors["base"] = (
                await self._async_authenticate_data(
                    {
                        **user_input,
                        CONF_EXCLUDE_WIRED: DEFAULT_EXCLUDE_WIRED,
                    }
                )
                or ""
            )
            if not errors["base"]:
                self._data = user_input
                return await self.async_step_wifi_filter()

        schema = vol.Schema(
            {
                vol.Required(CONF_TWIBI_IP_ADDRESS, default=DEFAULT_TWIBI_IP_ADDRESS): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_wifi_filter(self, user_input=None):
        """Handle the WiFi filter selection step."""
        errors = {}

        if user_input is not None:
            exclude_wired = user_input.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED)
            self._data[CONF_EXCLUDE_WIRED] = exclude_wired

            if self._api:
                self._api.exclude_wired = exclude_wired

            return await self.async_step_select_devices()

        schema = vol.Schema({
            vol.Optional(
                CONF_EXCLUDE_WIRED,
                default=self._data.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED)
            ): bool,
        })

        return self.async_show_form(
            step_id="wifi_filter",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "description": "Selecionar esta opção limitará a lista de dispositivos aos conectados via Wi-Fi."
            },
        )

    async def async_step_select_devices(self, user_input=None):
        """Handle the device selection step."""
        errors = {}

        if not self._devices:
            max_retries = 3
            retry_delay = 10
            errors["base"] = ""
            for attempt in range(max_retries):
                try:
                    if self._api is None:
                        errors["base"] = "API não inicializada."
                        return self.async_show_form(
                            step_id="select_devices",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

                    self._devices = await self._api.get_online_devices()

                    if not self._devices:
                        errors["base"] = "Nenhum dispositivo encontrado com o filtro atual. Desmarque a opção de Wi-Fi apenas ou conecte um dispositivo e tente novamente."
                        return self.async_show_form(
                            step_id="select_devices",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

                    break
                except AuthenticationError as ex:
                    _LOGGER.warning(
                        "Authentication error fetching devices (attempt %d/%d): %s Retrying",
                        attempt + 1,
                        max_retries,
                        ex
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        _LOGGER.error("Authentication failed after %d attempts: %s", max_retries, ex)
                        errors["base"] = "O roteador está instável. Aguarde alguns minutos e tente novamente. Se o problema persistir, reinicie o roteador."
                        return self.async_show_form(
                            step_id="select_devices",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )
                except Exception as ex:
                    _LOGGER.warning(
                        "Error fetching devices (attempt %d/%d): %s. Retrying",
                        attempt + 1,
                        max_retries,
                        ex
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        _LOGGER.error("Failed to fetch devices after %d attempts: %s", max_retries, ex)
                        errors["base"] = f"Erro ao buscar dispositivos após {max_retries} tentativas."
                        return self.async_show_form(
                            step_id="select_devices",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

        if user_input is not None:
            selected_macs = user_input.get(CONF_SELECTED_DEVICES, [])

            self._data[CONF_SELECTED_DEVICES] = selected_macs
            self._data[CONF_TRACK_ALL_DEVICES] = not selected_macs

            return self.async_create_entry(
                title=f"Twibi ({self._data[CONF_TWIBI_IP_ADDRESS]})",
                data=self._data
            )

        mac_to_name = {
            dev.mac: _device_option_label(dev)
            for dev in self._devices
        }

        schema = vol.Schema({
            vol.Optional(
                CONF_SELECTED_DEVICES,
                default=[]
            ): _device_select_selector(mac_to_name),
        })

        return self.async_show_form(
            step_id="select_devices",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._devices)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TwibiOptionsFlow(config_entry)

    async def async_step_reauth(self, entry_data):
        """Start reauth when stored credentials are no longer valid."""
        self._data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle the credential update step for reauth."""
        errors = {}

        if user_input is not None:
            reauth_data = {
                **self._data,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            errors["base"] = await self._async_authenticate_data(reauth_data) or ""
            if not errors["base"]:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )


class TwibiOptionsFlow(OptionsFlow):
    """Handle options flow for the Twibi integration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_data = dict(config_entry.data)
        self._entry = config_entry
        self._api = None
        self._devices: list[OnlineDevice] = []

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_wifi_filter(user_input)

    async def async_step_wifi_filter(self, user_input=None):
        """Handle the WiFi filter selection step in options flow."""
        errors = {}

        if user_input is not None:
            exclude_wired = user_input.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED)
            self._temp_data = {CONF_EXCLUDE_WIRED: exclude_wired}

            return await self.async_step_device_selection()

        schema = vol.Schema({
            vol.Optional(
                CONF_EXCLUDE_WIRED,
                default=self._config_data.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED)
            ): bool,
        })

        return self.async_show_form(
            step_id="wifi_filter",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "description": "Selecionar esta opção limitará a lista de dispositivos aos conectados via Wi-Fi."
            },
        )

    async def async_step_device_selection(self, user_input=None):
        """Handle the device selection step."""
        errors = {}

        if not self._devices:
            session = async_get_clientsession(self.hass)
            exclude_wired = self._temp_data.get(CONF_EXCLUDE_WIRED, self._config_data.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED))
            self._api = TwibiAPI(
                self._config_data[CONF_TWIBI_IP_ADDRESS],
                self._config_data[CONF_PASSWORD],
                bool(exclude_wired),
                self._config_data[CONF_UPDATE_INTERVAL],
                session
            )

            max_retries = 3
            retry_delay = 10
            errors["base"] = ""
            for attempt in range(max_retries):
                try:
                    if self._api is None:
                        errors["base"] = "API não inicializada."
                        return self.async_show_form(
                            step_id="device_selection",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

                    self._devices = await self._api.get_online_devices()

                    if not self._devices:
                        errors["base"] = "Nenhum dispositivo encontrado com o filtro atual. Desmarque a opção de Wi-Fi apenas ou conecte um dispositivo e tente novamente."
                        return self.async_show_form(
                            step_id="device_selection",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

                    break
                except Exception as ex:
                    _LOGGER.warning(
                        "Error fetching devices (attempt %d/%d): %s. Retrying",
                        attempt + 1,
                        max_retries,
                        ex
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        _LOGGER.error("Failed to fetch devices after %d attempts: %s", max_retries, ex)
                        errors["base"] = f"Erro ao buscar dispositivos após {max_retries} tentativas."
                        return self.async_show_form(
                            step_id="device_selection",
                            data_schema=vol.Schema({}),
                            errors=errors,
                        )

        if user_input is not None:
            selected_macs = user_input.get(CONF_SELECTED_DEVICES, [])
            selected_mac_set = set(selected_macs)
            current_selected = self._config_data.get(CONF_SELECTED_DEVICES, [])
            was_tracking_all = self._config_data.get(
                CONF_TRACK_ALL_DEVICES,
                not current_selected,
            )
            available_option_macs = {dev.mac for dev in self._devices}
            track_all_devices = (
                bool(available_option_macs)
                and was_tracking_all
                and selected_mac_set == available_option_macs
            )

            new_data = dict(self._config_data)
            new_data[CONF_SELECTED_DEVICES] = selected_macs
            new_data[CONF_TRACK_ALL_DEVICES] = track_all_devices
            new_data[CONF_EXCLUDE_WIRED] = self._temp_data.get(CONF_EXCLUDE_WIRED, new_data.get(CONF_EXCLUDE_WIRED, DEFAULT_EXCLUDE_WIRED))

            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )
            _remove_deselected_trackers(
                self.hass,
                self._entry.entry_id,
                selected_mac_set,
                track_all_devices,
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)

            return self.async_create_entry(title="", data={})

        current_selected = self._config_data.get(CONF_SELECTED_DEVICES, [])
        track_all_devices = self._config_data.get(
            CONF_TRACK_ALL_DEVICES,
            not current_selected,
        )

        mac_to_name = {
            dev.mac: _device_option_label(dev)
            for dev in self._devices
        }

        for mac in current_selected:
            mac_to_name.setdefault(
                mac,
                _device_option_label(
                    {
                        "dev_mac": mac,
                        "dev_name": f"Previously selected {mac}",
                        "dev_ip": None,
                        "connection": "Offline",
                    }
                ),
            )

        available_option_macs = list(mac_to_name)
        default_selected = (
            available_option_macs
            if track_all_devices
            else current_selected
        )

        schema = vol.Schema({
            vol.Optional(
                CONF_SELECTED_DEVICES,
                default=default_selected
            ): _device_select_selector(mac_to_name),
        })

        return self.async_show_form(
            step_id="device_selection",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._devices)),
            },
        )
