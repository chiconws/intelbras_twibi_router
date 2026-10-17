"""TwibiClient against a mocked router."""

import pytest
from aiohttp import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.intelbras_twibi import api
from custom_components.intelbras_twibi.api import (
    RouterData,
    TwibiAuthError,
    TwibiClient,
    TwibiConnectionError,
    TwibiError,
)

BASE = "http://192.168.5.1/goform"
SET = f"{BASE}/set"
LOGIN_PAGE = "<!DOCTYPE html><html>login</html>"


def get_url(*modules: str) -> str:
    return f"{BASE}/get?module_id={','.join(modules)}"


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(api, "OPTIONAL_MODULE_DELAY", 0)


def mock_router(aioclient_mock: AiohttpClientMocker, payload: dict, **login) -> None:
    aioclient_mock.post(SET, json={"errcode": "0"}, **login)
    aioclient_mock.get(get_url(*api.CORE_MODULES), json={k: payload[k] for k in api.CORE_MODULES})
    for module in api.OPTIONAL_MODULES:
        aioclient_mock.get(get_url(module), json={module: payload[module]})


def make_client(hass: HomeAssistant) -> TwibiClient:
    return TwibiClient("192.168.5.1", "secret", async_get_clientsession(hass))


async def test_get_data_parses_everything(hass, aioclient_mock, payload) -> None:
    mock_router(aioclient_mock, payload)
    data = await make_client(hass).async_get_data()

    assert data.primary.serial == "TWIBI0000PRIM"
    assert data.primary.led_on and data.primary.wan_connected and data.primary.uptime == 17658
    secondary = data.nodes[1]
    assert not secondary.is_primary and secondary.link_quality == -82 and not secondary.led_on
    assert data.clients["11:22:33:44:55:01"].band == "5ghz"
    assert data.clients["11:22:33:44:55:02"].band == "wired"
    assert (data.wan_download, data.wan_upload, data.wan_ip) == (2400.0, 120.0, "100.64.0.10")
    assert data.guest and data.guest.ssid == "Visitors" and not data.guest.enabled
    assert data.upnp_enabled is True
    login = aioclient_mock.mock_calls[0][2]["login"]
    assert login["pwd"] == "5ebe2294ecd0e0f08eab7690d2a6ee69"  # md5("secret")


async def test_optional_module_failure_is_skipped(hass, aioclient_mock, payload) -> None:
    aioclient_mock.post(SET, json={"errcode": "0"})
    aioclient_mock.get(get_url(*api.CORE_MODULES), json={k: payload[k] for k in api.CORE_MODULES})
    for module in api.OPTIONAL_MODULES:
        aioclient_mock.get(get_url(module), text="not json")
    data = await make_client(hass).async_get_data()
    assert data.guest is None and data.upnp_enabled is None and data.wan_ip is None


async def test_wrong_password(hass, aioclient_mock) -> None:
    aioclient_mock.post(SET, json={"errcode": "1"})
    with pytest.raises(TwibiAuthError):
        await make_client(hass).async_login()


async def test_unreachable(hass, aioclient_mock) -> None:
    aioclient_mock.post(SET, exc=ClientError())
    with pytest.raises(TwibiConnectionError):
        await make_client(hass).async_login()


@pytest.mark.parametrize("text", ["", "{broken"])
async def test_bad_reply(hass, aioclient_mock, text) -> None:
    aioclient_mock.post(SET, text=text)
    with pytest.raises(TwibiError):
        await make_client(hass).async_login()


async def test_no_nodes_is_an_error(hass, aioclient_mock) -> None:
    aioclient_mock.post(SET, json={"errcode": "0"})
    aioclient_mock.get(get_url(*api.CORE_MODULES), json={"node_info": []})
    with pytest.raises(TwibiError, match="no mesh nodes"):
        await make_client(hass).async_get_data()


async def test_login_page_twice_gives_up(hass, aioclient_mock) -> None:
    aioclient_mock.post(SET, json={"errcode": "0"})
    aioclient_mock.get(get_url(*api.CORE_MODULES), text=LOGIN_PAGE)
    with pytest.raises(TwibiError, match="login page"):
        await make_client(hass).async_get_data()
    assert sum(1 for c in aioclient_mock.mock_calls if c[0] == "POST") == 2  # logged in again once


async def test_session_cookie_is_sent_as_header(hass, aioclient_mock, payload) -> None:
    mock_router(aioclient_mock, payload, cookies={"MESH_user": "abc"})
    await make_client(hass).async_get_data()
    get_headers = aioclient_mock.mock_calls[1][3]
    assert get_headers == {"Cookie": "MESH_user=abc"}


async def test_commands(hass, aioclient_mock, payload) -> None:
    aioclient_mock.post(SET, json={"errcode": "0"})
    client = make_client(hass)
    guest = RouterData.from_dict(payload).guest
    assert guest
    await client.async_set_led("SN1", False)
    await client.async_set_upnp(True)
    await client.async_set_guest(guest, True)
    await client.async_reboot()
    bodies = [c[2] for c in aioclient_mock.mock_calls[1:]]
    assert bodies[0]["led"]["led_en"] == "0" and bodies[0]["led"]["sn"] == "SN1"
    assert bodies[1]["upnp_info"]["upnp_en"] == "1"
    assert bodies[2]["guest_info"] | {"timestamp": None} == {
        "guest_en": "1",
        "guest_ssid": "Visitors",
        "guest_pass": "guestsecret",
        "guest_time": "always",
        "limit": "0",
        "timestamp": None,
    }
    assert bodies[3]["sys_reboot"]["action"] == "reboot"


async def test_rejected_command(hass, aioclient_mock) -> None:
    client = make_client(hass)
    aioclient_mock.post(SET, json={"errcode": "0"})
    await client.async_login()
    aioclient_mock.clear_requests()
    aioclient_mock.post(SET, json={"errcode": "7"})
    with pytest.raises(TwibiError, match="errcode 7"):
        await client.async_reboot()
