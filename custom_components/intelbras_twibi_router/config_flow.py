"""Config flow for Twibi Router integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APIError, TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_TWIBI_IP_ADDRESS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TWIBI_IP_ADDRESS, default=DEFAULT_TWIBI_IP_ADDRESS): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_EXCLUDE_WIRED, default=True): bool,
        vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int
    }
)

class TwibiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twibi Tracker."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_TWIBI_IP_ADDRESS]
            password = user_input[CONF_PASSWORD]
            _LOGGER.debug("Connecting to Twibi at %s", host)
            session = async_get_clientsession(self.hass)

            try:
                twibi = TwibiAPI(host, password, user_input[CONF_EXCLUDE_WIRED], user_input[CONF_UPDATE_INTERVAL], session)
                await twibi.login()
                await twibi.get_online_list()

                return self.async_create_entry(title=f"Twibi ({host})", data=user_input)

            except APIError as err:
                _LOGGER.error("Error connecting to Twibi: %s", err)
                errors["base"] = "Endereço IP ou senha inválidos."

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
