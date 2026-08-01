"""Tests for the CountryMod coordinator against a fake BLE client.

These cover the behaviour that only shows up on real hardware: notifications
arrive fragmented, a completed write is not proof the controller acted, and a
silent controller must drop the connection rather than serve stale state.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from bleak.exc import BleakError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.countrymod_ac.const import DOMAIN
from custom_components.countrymod_ac.coordinator import CountryModCoordinator
from custom_components.countrymod_ac.protocol import Command, build_command

ADDRESS = "AA:BB:CC:DD:EE:FF"


def build_state_frame(target: int = 75, fan: int = 3, power: bool = True) -> bytes:
    """Build a state frame shaped like the ones the controller sends."""
    status = (0x80 if power else 0x00) | (1 << 4) | (fan << 1) | 1
    body = bytearray(
        [
            0x5A,
            0x5A,
            status,
            0x40,
            73,  # inlet
            22,  # coil
            0,
            0,
            13,  # volts
            90,  # under-voltage, decivolts
            0,  # fault
            0,  # timer
            0,
            0,
            0,
            0,
            1,  # Fahrenheit
            target,
        ]
    )
    return bytes(body + bytes([sum(body) & 0xFF]) + b"\x0d\x0a")


class FakeClient:
    """Stands in for a connected BleakClient.

    It answers any write whose value byte is 0 (a query) with a state frame,
    delivered in fragments the way the real controller does.
    """

    def __init__(self) -> None:
        self.is_connected = True
        self.writes: list[bytes] = []
        self.notify_cb = None
        self.disconnected = False
        self.target = 75
        self.fan = 3
        self.power = True
        self.answer_queries = True

    async def start_notify(self, _uuid, callback):
        self.notify_cb = callback

    async def stop_notify(self, _uuid):
        self.notify_cb = None

    async def disconnect(self):
        self.is_connected = False
        self.disconnected = True

    def _emit(self, frame: bytes) -> None:
        # Mirror the observed 10-byte / 1-byte fragmentation.
        for start in range(0, len(frame), 10):
            self.notify_cb(None, bytearray(frame[start : start + 10]))

    async def write_gatt_char(self, _uuid, data, response=False):
        self.writes.append(bytes(data))
        code, value = data[4], data[5]
        if value != 0:
            # Apply the command, as the real controller would.
            if code == Command.TARGET_TEMPERATURE:
                self.target = value
            elif code == Command.FAN_SPEED:
                self.fan = value
            elif code == Command.POWER:
                self.power = value == 2
            return
        if self.answer_queries and self.notify_cb is not None:
            self._emit(build_state_frame(self.target, self.fan, self.power))


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def coordinator(hass: HomeAssistant, fake_client: FakeClient):
    """A coordinator wired to the fake client."""
    entry = MockConfigEntry(domain=DOMAIN, title="KT2000000000000")
    entry.add_to_hass(hass)
    coordinator = CountryModCoordinator(
        hass, entry, address=ADDRESS, kind_code=1, scan_interval=15
    )
    with (
        patch(
            "custom_components.countrymod_ac.coordinator.bluetooth"
            ".async_ble_device_from_address",
            return_value=object(),
        ),
        patch(
            "custom_components.countrymod_ac.coordinator.establish_connection",
            return_value=fake_client,
        ),
    ):
        yield coordinator


async def test_refresh_decodes_fragmented_state(coordinator, fake_client):
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.target_temperature == 75
    assert coordinator.data.fan_speed == 3
    # It subscribed before querying.
    assert fake_client.notify_cb is not None
    assert fake_client.writes == [build_command(Command.REFRESH, 0, 1)]


async def test_command_is_confirmed_by_a_fresh_state_frame(coordinator, fake_client):
    await coordinator.async_refresh()
    state = await coordinator.async_send_command(Command.TARGET_TEMPERATURE, 76)

    assert state.target_temperature == 76
    assert coordinator.data.target_temperature == 76
    # One command frame, then a query to confirm it.
    assert fake_client.writes[-2] == build_command(Command.TARGET_TEMPERATURE, 76, 1)
    assert fake_client.writes[-1] == build_command(Command.REFRESH, 0, 1)


async def test_connection_is_reused_across_refreshes(coordinator, fake_client):
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    assert len(fake_client.writes) == 2
    assert not fake_client.disconnected


async def test_silence_after_query_drops_the_connection(coordinator, fake_client):
    await coordinator.async_refresh()
    fake_client.answer_queries = False

    with patch("custom_components.countrymod_ac.coordinator.STATE_TIMEOUT", 0.05):
        await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert fake_client.disconnected


async def test_write_failure_surfaces_as_update_failed(coordinator, fake_client):
    await coordinator.async_refresh()

    async def boom(*args, **kwargs):
        raise BleakError("link lost")

    fake_client.write_gatt_char = boom
    with pytest.raises(UpdateFailed):
        await coordinator.async_send_command(Command.POWER, 1)
    assert fake_client.disconnected


async def test_failed_subscription_does_not_leak_a_connection(
    hass: HomeAssistant, fake_client: FakeClient
):
    entry = MockConfigEntry(domain=DOMAIN, title="KT")
    entry.add_to_hass(hass)
    coordinator = CountryModCoordinator(
        hass, entry, address=ADDRESS, kind_code=1, scan_interval=15
    )

    async def boom(*args, **kwargs):
        raise BleakError("no such characteristic")

    fake_client.start_notify = boom
    with (
        patch(
            "custom_components.countrymod_ac.coordinator.bluetooth"
            ".async_ble_device_from_address",
            return_value=object(),
        ),
        patch(
            "custom_components.countrymod_ac.coordinator.establish_connection",
            return_value=fake_client,
        ),
    ):
        await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert fake_client.disconnected


async def test_out_of_range_controller_fails_cleanly(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, title="KT")
    entry.add_to_hass(hass)
    coordinator = CountryModCoordinator(
        hass, entry, address=ADDRESS, kind_code=1, scan_interval=15
    )
    with patch(
        "custom_components.countrymod_ac.coordinator.bluetooth"
        ".async_ble_device_from_address",
        return_value=None,
    ):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success


async def test_commands_are_serialised(coordinator, fake_client):
    """Two concurrent commands must not interleave on the wire."""
    await coordinator.async_refresh()
    fake_client.writes.clear()

    await asyncio.gather(
        coordinator.async_send_command(Command.TARGET_TEMPERATURE, 76),
        coordinator.async_send_command(Command.FAN_SPEED, 4),
    )

    # Each command is immediately followed by its own confirming query.
    assert len(fake_client.writes) == 4
    for index in (0, 2):
        assert fake_client.writes[index][5] != 0
        assert fake_client.writes[index + 1] == build_command(Command.REFRESH, 0, 1)


async def test_kind_code_is_used_in_every_frame(hass: HomeAssistant, fake_client):
    entry = MockConfigEntry(domain=DOMAIN, title="KT")
    entry.add_to_hass(hass)
    coordinator = CountryModCoordinator(
        hass, entry, address=ADDRESS, kind_code=3, scan_interval=15
    )
    with (
        patch(
            "custom_components.countrymod_ac.coordinator.bluetooth"
            ".async_ble_device_from_address",
            return_value=object(),
        ),
        patch(
            "custom_components.countrymod_ac.coordinator.establish_connection",
            return_value=fake_client,
        ),
    ):
        await coordinator.async_refresh()

    assert fake_client.writes[0] == build_command(Command.REFRESH, 0, 3)


async def test_disconnect_is_idempotent(coordinator, fake_client):
    await coordinator.async_refresh()
    await coordinator.async_disconnect()
    await coordinator.async_disconnect()
    assert fake_client.disconnected
