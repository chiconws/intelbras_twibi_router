"""Config flow: router address and password; options pick the tracked clients."""

from __future__ import annotations

import logging
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import RouterData, TwibiAuthError, TwibiClient, TwibiConnectionError, TwibiError
from .const import CONF_TRACKED_DEVICES, CONF_WIFI_ONLY, DEFAULT_HOST, DOMAIN
from .coordinator import TwibiConfigEntry

_LOGGER = logging.getLogger(__name__)

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class TwibiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Twibi mesh."""

    VERSION = 1

    async def _async_try(self, host: str, password: str) -> tuple[RouterData | None, dict[str, str]]:
        """Log in and read the router; return the snapshot or form errors."""
        client = TwibiClient(host, password, async_get_clientsession(self.hass))
        try:
            await client.async_login()
            return await client.async_get_data(), {}
        except TwibiAuthError:
            return None, {"base": "invalid_auth"}
        except TwibiConnectionError:
            return None, {"base": "cannot_connect"}
        except TwibiError:
            _LOGGER.exception("Unexpected reply from the router")
            return None, {"base": "unknown"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the router address and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._async_try(user_input[CONF_HOST], user_input[CONF_PASSWORD])
            if data:
                await self.async_set_unique_id(data.primary.serial)
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title=f"Twibi {data.primary.model}", data=user_input)
        schema = vol.Schema(
            {vol.Required(CONF_HOST, default=DEFAULT_HOST): str, vol.Required(CONF_PASSWORD): PASSWORD}
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """The stored password stopped working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._async_try(entry.data[CONF_HOST], user_input[CONF_PASSWORD])
            if data:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the router address or password."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._async_try(user_input[CONF_HOST], user_input[CONF_PASSWORD])
            if data:
                await self.async_set_unique_id(data.primary.serial)
                self._abort_if_unique_id_mismatch(reason="wrong_router")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        schema = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_PASSWORD): PASSWORD})
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or entry.data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: TwibiConfigEntry) -> TwibiOptionsFlow:
        """Choose which clients to track."""
        return TwibiOptionsFlow()


class TwibiOptionsFlow(OptionsFlow):
    """Pick tracked clients from the ones online now."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the client list."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry: TwibiConfigEntry = self.config_entry
        clients = entry.runtime_data.data.clients
        selected: list[str] = entry.options.get(CONF_TRACKED_DEVICES, [])
        options = [
            SelectOptionDict(value=mac, label=f"{c.name or mac} ({c.ip}, {c.band})")
            for mac, c in sorted(clients.items(), key=lambda i: (i[1].name or i[0]).lower())
        ] + [SelectOptionDict(value=mac, label=mac) for mac in selected if mac not in clients]
        schema = vol.Schema(
            {
                vol.Required(CONF_WIFI_ONLY, default=entry.options.get(CONF_WIFI_ONLY, False)): bool,
                vol.Optional(CONF_TRACKED_DEVICES, default=selected): SelectSelector(
                    SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
