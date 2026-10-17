"""Shared pytest fixtures."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelbras_twibi.api import RouterData
from custom_components.intelbras_twibi.const import DOMAIN

PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "router.json").read_text())
ENTRY_DATA = {CONF_HOST: "192.168.5.1", CONF_PASSWORD: "secret"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load custom_components/ during tests."""
    yield


@pytest.fixture
def payload() -> dict:
    """A fresh copy of the anonymised router reply."""
    return json.loads(json.dumps(PAYLOAD))


@pytest.fixture
def client(payload):
    """Replace TwibiClient everywhere with a mock that serves the fixture."""
    with (
        patch("custom_components.intelbras_twibi.TwibiClient", autospec=True) as cls,
        patch("custom_components.intelbras_twibi.config_flow.TwibiClient", new=cls),
    ):
        mock = cls.return_value
        mock.async_get_data = AsyncMock(side_effect=lambda: RouterData.from_dict(payload))
        yield mock


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A configured Twibi entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="TWIBI0000PRIM", data=ENTRY_DATA, title="Twibi")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def loaded(hass: HomeAssistant, entry: MockConfigEntry, client) -> MockConfigEntry:
    """The entry, set up."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
