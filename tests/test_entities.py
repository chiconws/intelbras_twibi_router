"""Entity states and commands."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.intelbras_twibi.api import TwibiConnectionError, TwibiError
from custom_components.intelbras_twibi.const import CONF_TRACKED_DEVICES, CONF_WIFI_ONLY

PRIMARY = "twibi_fast_prim"
SECONDARY = "twibi_fast_sec2"


def state(hass: HomeAssistant, entity_id: str) -> str:
    current = hass.states.get(entity_id)
    assert current, f"{entity_id} does not exist"
    return current.state


async def test_states(hass: HomeAssistant, loaded) -> None:
    assert state(hass, f"sensor.{PRIMARY}_download_speed") == "2400.0"
    assert state(hass, f"sensor.{PRIMARY}_upload_speed") == "120.0"
    assert state(hass, f"sensor.{PRIMARY}_connected_clients") == "2"
    assert state(hass, f"sensor.{PRIMARY}_wan_ip_address") == "100.64.0.10"
    assert state(hass, f"sensor.{SECONDARY}_mesh_link_quality") == "-82"
    assert state(hass, f"binary_sensor.{PRIMARY}_internet") == STATE_ON
    assert state(hass, f"light.{PRIMARY}_status_led") == STATE_ON
    assert state(hass, f"light.{SECONDARY}_status_led") == STATE_OFF
    assert state(hass, f"switch.{PRIMARY}_guest_wi_fi") == STATE_OFF
    assert state(hass, f"switch.{PRIMARY}_upnp") == STATE_ON
    assert hass.states.get(f"sensor.{PRIMARY}_last_boot") is not None


async def test_uptime_is_stable_and_follows_reboots(
    hass: HomeAssistant, loaded, payload, freezer: FrozenDateTimeFactory
) -> None:
    entity_id = f"sensor.{PRIMARY}_last_boot"
    first = state(hass, entity_id)
    payload["node_info"][0]["Uptime"] = str(17658 + 33)  # 30 s poll + jitter
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, entity_id) == first

    payload["node_info"][0]["Uptime"] = "10"  # rebooted
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, entity_id) != first


async def test_trackers_follow_online_list(hass: HomeAssistant, loaded, payload, freezer) -> None:
    registry = er.async_get(hass)
    phone = registry.async_get_entity_id("device_tracker", "intelbras_twibi", "11:22:33:44:55:01")
    tracker = registry.async_get(phone) if phone else None
    assert phone and tracker and tracker.disabled_by is not None  # HA default for unknown MACs

    registry.async_update_entity(phone, disabled_by=None)
    await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    assert state(hass, phone) == STATE_HOME

    payload["online_list"] = payload["online_list"][1:]
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, phone) == STATE_NOT_HOME


async def test_chosen_trackers_are_enabled(hass: HomeAssistant, entry, client) -> None:
    hass.config_entries.async_update_entry(
        entry, options={CONF_TRACKED_DEVICES: ["11:22:33:44:55:02"], CONF_WIFI_ONLY: True}
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    trackers = [s for s in hass.states.async_entity_ids("device_tracker")]
    assert len(trackers) == 1
    tracker = hass.states.get(trackers[0])
    assert tracker and tracker.attributes["connection"] == "wired"


async def test_wifi_only_skips_wired(hass: HomeAssistant, entry, client) -> None:
    hass.config_entries.async_update_entry(entry, options={CONF_WIFI_ONLY: True})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("device_tracker", "intelbras_twibi", "11:22:33:44:55:02") is None


async def test_commands(hass: HomeAssistant, loaded, client, payload) -> None:
    await hass.services.async_call("light", "turn_off", {"entity_id": f"light.{PRIMARY}_status_led"}, blocking=True)
    client.async_set_led.assert_awaited_with("TWIBI0000PRIM", False)
    await hass.services.async_call("light", "turn_on", {"entity_id": f"light.{SECONDARY}_status_led"}, blocking=True)
    client.async_set_led.assert_awaited_with("TWIBI0000SEC2", True)

    await hass.services.async_call("switch", "turn_on", {"entity_id": f"switch.{PRIMARY}_guest_wi_fi"}, blocking=True)
    guest, on = client.async_set_guest.await_args.args
    assert guest.ssid == "Visitors" and on is True
    await hass.services.async_call("switch", "turn_off", {"entity_id": f"switch.{PRIMARY}_upnp"}, blocking=True)
    client.async_set_upnp.assert_awaited_with(False)

    await hass.services.async_call("button", "press", {"entity_id": f"button.{PRIMARY}_reboot_mesh"}, blocking=True)
    client.async_reboot.assert_awaited_once()


async def test_command_failure_is_reported(hass: HomeAssistant, loaded, client) -> None:
    client.async_reboot.side_effect = TwibiError("errcode 7")
    with pytest.raises(HomeAssistantError, match="errcode 7"):
        await hass.services.async_call("button", "press", {"entity_id": f"button.{PRIMARY}_reboot_mesh"}, blocking=True)


async def test_unavailable_when_router_down(hass: HomeAssistant, loaded, client, freezer) -> None:
    client.async_get_data.side_effect = TwibiConnectionError("down")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert state(hass, f"sensor.{PRIMARY}_download_speed") == STATE_UNAVAILABLE


async def test_missing_settings_hide_switches(hass: HomeAssistant, entry, client, payload) -> None:
    del payload["guest_info"], payload["upnp_info"]
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("switch") == []
