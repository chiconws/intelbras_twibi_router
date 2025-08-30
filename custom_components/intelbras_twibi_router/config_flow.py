"""Config flow for Twibi Router integration."""
from __future__ import annotations

import asyncio
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APIError, TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_SELECTED_DEVICES,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    MODULES,
)

_LOGGER = logging.getLogger(__name__)


class TwibiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twibi Tracker."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._data = {}
        self._devices = []
        self._api = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_TWIBI_IP_ADDRESS]
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)

            try:
                self._api = TwibiAPI(
                    host,
                    password,
                    True,
                    user_input[CONF_UPDATE_INTERVAL],
                    session
                )
                await self._api.login()

                self._data = user_input

                return await self.async_step_wifi_filter()

            except APIError:
                errors["base"] = "Endereço IP ou senha inválidos."

        schema = vol.Schema(
            {
                vol.Required(CONF_TWIBI_IP_ADDRESS, default="192.168.5.1"): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_UPDATE_INTERVAL, default=30): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_wifi_filter(self, user_input=None):
        """Handle the WiFi filter selection step."""
        errors = {}

        if user_input is not None:
            exclude_wired = user_input.get(CONF_EXCLUDE_WIRED, True)
            self._data[CONF_EXCLUDE_WIRED] = exclude_wired

            if self._api:
                self._api.exclude_wired = exclude_wired

            return await self.async_step_select_devices()

        schema = vol.Schema({
            vol.Optional(
                CONF_EXCLUDE_WIRED,
                default=self._data.get(CONF_EXCLUDE_WIRED, True)
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

                    data = await self._api.get_modules(MODULES)
                    online_devices = data.get("online_list", [])

                    if self._data.get(CONF_EXCLUDE_WIRED, True):
                        online_devices = [
                            dev for dev in online_devices
                            if dev.get("wifi_mode") != "--"
                        ]

                    self._devices = [
                        {
                            "dev_mac": dev["dev_mac"],
                            "dev_name": dev["dev_name"] or f"Device {dev['dev_mac']}",
                            "dev_ip": dev["dev_ip"],
                            "connection": "Ethernet" if dev.get("wifi_mode") == "--" else
                                         "5GHz" if dev.get("wifi_mode") == "AC" else
                                         "2.4GHz" if dev.get("wifi_mode") == "BGN" else "",
                        }
                        for dev in online_devices
                    ]
                    break
                except Exception as ex:
                    _LOGGER.warning(
                        "Error fetching devices (attempt %d/%d): %s. Retrying...",
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

            return self.async_create_entry(
                title=f"Twibi ({self._data[CONF_TWIBI_IP_ADDRESS]})",
                data=self._data
            )

        mac_to_name = {
            dev["dev_mac"]: f"{dev['dev_name']} ({dev['dev_ip']}, {dev['connection']})"
            for dev in self._devices
        }

        schema = vol.Schema({
            vol.Optional(
                CONF_SELECTED_DEVICES,
                default=[]
            ): cv.multi_select(mac_to_name),
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


class TwibiOptionsFlow(OptionsFlow):
    """Handle options flow for the Twibi integration."""

    def __init__(self, config_entry: ConfigEntry):
        """Initialize options flow."""
        self._config_data = dict(config_entry.data)
        self._entry = config_entry
        self._api = None
        self._devices = []

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_wifi_filter(user_input)

    async def async_step_wifi_filter(self, user_input=None):
        """Handle the WiFi filter selection step in options flow."""
        errors = {}

        if user_input is not None:
            exclude_wired = user_input.get(CONF_EXCLUDE_WIRED, True)
            self._temp_data = {CONF_EXCLUDE_WIRED: exclude_wired}

            return await self.async_step_device_selection()

        schema = vol.Schema({
            vol.Optional(
                CONF_EXCLUDE_WIRED,
                default=self._config_data.get(CONF_EXCLUDE_WIRED, True)
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
            exclude_wired = self._temp_data.get(CONF_EXCLUDE_WIRED, self._config_data.get(CONF_EXCLUDE_WIRED, True))
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

                    await self._api.login()
                    data = await self._api.get_modules(MODULES)
                    online_devices = data.get("online_list", [])

                    if self._temp_data.get(CONF_EXCLUDE_WIRED, self._config_data.get(CONF_EXCLUDE_WIRED, True)):
                        online_devices = [
                            dev for dev in online_devices
                            if dev.get("wifi_mode") != "--"
                        ]

                    self._devices = [
                        {
                            "dev_mac": dev["dev_mac"],
                            "dev_name": dev["dev_name"] or f"Device {dev['dev_mac']}",
                            "dev_ip": dev["dev_ip"],
                            "connection": "Ethernet" if dev.get("wifi_mode") == "--" else
                                         "5GHz" if dev.get("wifi_mode") == "AC" else
                                         "2.4GHz" if dev.get("wifi_mode") == "BGN" else "",
                        }
                        for dev in online_devices
                    ]
                    break
                except Exception as ex:
                    _LOGGER.warning(
                        "Error fetching devices (attempt %d/%d): %s. Retrying...",
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

            new_data = dict(self._config_data)
            new_data[CONF_SELECTED_DEVICES] = selected_macs
            new_data[CONF_EXCLUDE_WIRED] = self._temp_data.get(CONF_EXCLUDE_WIRED, new_data.get(CONF_EXCLUDE_WIRED, True))

            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data
            )

            return self.async_create_entry(title="", data={})

        current_selected = self._config_data.get(CONF_SELECTED_DEVICES, [])

        mac_to_name = {
            dev["dev_mac"]: f"{dev['dev_name']} ({dev['dev_ip']}, {dev['connection']})"
            for dev in self._devices
        }

        schema = vol.Schema({
            vol.Optional(
                CONF_SELECTED_DEVICES,
                default=current_selected
            ): cv.multi_select(mac_to_name),
        })

        return self.async_show_form(
            step_id="device_selection",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._devices)),
            },
        )
