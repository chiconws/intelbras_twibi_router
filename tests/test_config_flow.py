"""Config, reauth, reconfigure and options flows."""

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.intelbras_twibi.api import (
    TwibiAuthError,
    TwibiConnectionError,
    TwibiError,
)
from custom_components.intelbras_twibi.const import CONF_TRACKED_DEVICES, CONF_WIFI_ONLY, DOMAIN

from .conftest import ENTRY_DATA


async def test_user_creates_entry(hass: HomeAssistant, client) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Twibi Twibi Fast"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == "TWIBI0000PRIM"


@pytest.mark.parametrize(
    ("exc", "error"),
    [(TwibiAuthError, "invalid_auth"), (TwibiConnectionError, "cannot_connect"), (TwibiError, "unknown")],
)
async def test_user_errors_then_recovers(hass: HomeAssistant, client, exc, error) -> None:
    client.async_login.side_effect = exc
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["errors"] == {"base": error}

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_already_configured(hass: HomeAssistant, client, entry) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT  # single_config_entry


async def test_reauth(hass: HomeAssistant, loaded, client) -> None:
    result = await loaded.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    client.async_login.side_effect = TwibiAuthError
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "bad"})
    assert result["errors"] == {"base": "invalid_auth"}

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
    assert result["reason"] == "reauth_successful"
    assert loaded.data[CONF_PASSWORD] == "new"


async def test_reconfigure(hass: HomeAssistant, loaded, client) -> None:
    result = await loaded.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    client.async_login.side_effect = TwibiConnectionError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.1", CONF_PASSWORD: "x"}
    )
    assert result["errors"] == {"base": "cannot_connect"}

    client.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.2", CONF_PASSWORD: "x"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert loaded.data[CONF_HOST] == "10.0.0.2"


async def test_reconfigure_other_router(hass: HomeAssistant, loaded, client, payload) -> None:
    for node in payload["node_info"]:
        node["sn"] = "OTHER" + node["sn"]
    result = await loaded.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["reason"] == "wrong_router"


async def test_options(hass: HomeAssistant, loaded) -> None:
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_WIFI_ONLY: True, CONF_TRACKED_DEVICES: ["11:22:33:44:55:01"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert loaded.options == {CONF_WIFI_ONLY: True, CONF_TRACKED_DEVICES: ["11:22:33:44:55:01"]}
