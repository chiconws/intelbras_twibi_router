"""Setup, unload and polling failures."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.intelbras_twibi.api import TwibiAuthError, TwibiConnectionError


async def test_setup_and_unload(hass: HomeAssistant, loaded) -> None:
    assert loaded.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(loaded.entry_id)
    assert loaded.state is ConfigEntryState.NOT_LOADED


async def test_router_down_retries_setup(hass: HomeAssistant, entry, client) -> None:
    client.async_get_data.side_effect = TwibiConnectionError("down")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_password_starts_reauth(hass: HomeAssistant, entry, client) -> None:
    client.async_get_data.side_effect = TwibiAuthError
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
