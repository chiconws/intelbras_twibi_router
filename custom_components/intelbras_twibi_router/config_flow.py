"""Config flow for Twibi Router integration."""
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import APIError, TwibiAPI
from .const import (
    CONF_EXCLUDE_WIRED,
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    CONFIG_FLOW_SCHEMA,
    DOMAIN,
)


class TwibiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Twibi Tracker."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_TWIBI_IP_ADDRESS]
            password = user_input[CONF_PASSWORD]
            session = async_get_clientsession(self.hass)

            try:
                twibi = TwibiAPI(host, password, user_input[CONF_EXCLUDE_WIRED], user_input[CONF_UPDATE_INTERVAL], session)
                await twibi.login()

                return self.async_create_entry(title=f"Twibi ({host})", data=user_input)

            except APIError:
                errors["base"] = "Endereço IP ou senha inválidos."

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_FLOW_SCHEMA, errors=errors
        )
