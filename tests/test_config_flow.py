"""Config flow tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.intelbras_twibi.const import (
    CONF_PASSWORD,
    CONF_TWIBI_IP_ADDRESS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

USER_INPUT = {CONF_TWIBI_IP_ADDRESS: "192.0.2.1", CONF_PASSWORD: "x", CONF_UPDATE_INTERVAL: 30}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_wrong_password_shows_error(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(
        "custom_components.intelbras_twibi.config_flow.TwibiAPI.authenticate",
        AsyncMock(return_value=MagicMock(authenticated=False)),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"]


async def test_valid_credentials_advance_to_wifi_filter(hass: HomeAssistant) -> None:
    result = await _start(hass)
    with patch(
        "custom_components.intelbras_twibi.config_flow.TwibiAPI.authenticate",
        AsyncMock(return_value=MagicMock(authenticated=True)),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["step_id"] == "wifi_filter"
