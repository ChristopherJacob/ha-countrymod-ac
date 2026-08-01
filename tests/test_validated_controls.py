"""Decoder tests against frames captured after each validated command.

Every frame here is verbatim from the controller on 2026-08-01, recorded
immediately after the named command was written and confirmed to have taken
effect. See docs/protocol-discovery/command-validation.md.
"""

from __future__ import annotations

from custom_components.countrymod_ac.protocol import ModeState, decode_state


def h(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


AFTER_LIGHT_ON = h("5a 5a 97 42 47 15 00 00 0d 5a 00 00 00 00 00 00 01 4b 9c 0d 0a")
AFTER_LIGHT_VALUE_2 = h(
    "5a 5a 97 40 47 15 00 00 0d 5a 00 00 00 00 00 00 01 4b 9a 0d 0a"
)
AFTER_SWING_ON = h("5a 5a 97 48 47 15 00 00 0d 5a 00 00 00 00 00 00 01 4b a2 0d 0a")
AFTER_INTAKE_OUTER = h("5a 5a 97 41 47 15 00 00 0d 5a 00 00 00 00 00 00 01 4b 9b 0d 0a")
AFTER_UNIT_CELSIUS = h("5a 5a 97 40 16 16 00 00 0d 5a 00 00 00 00 00 00 00 17 35 0d 0a")
AFTER_TIMER_1H = h("5a 5a 97 40 47 16 00 00 0d 5a 00 01 00 00 00 3b 01 4b d7 0d 0a")
AFTER_MODE_DRY = h("5a 5a a3 40 49 16 00 00 0d 5a 00 00 00 00 00 00 01 4b a9 0d 0a")
AFTER_PRESET_ECO = h("5a 5a 83 20 49 16 00 00 0d 5a 00 00 00 00 00 00 01 4b 69 0d 0a")
AFTER_PRESET_SLEEP = h("5a 5a 93 10 49 16 00 00 0d 5a 00 00 00 00 00 00 01 4b 69 0d 0a")
AFTER_PRESET_TURBO = h("5a 5a 9b 80 49 16 00 00 0d 5a 00 00 00 00 00 00 01 4b e1 0d 0a")
AFTER_UVP_10V = h("5a 5a 97 40 47 16 00 00 0d 64 00 00 00 00 00 00 01 4b a5 0d 0a")


def test_light_on():
    assert decode_state(AFTER_LIGHT_ON).light is True


def test_light_command_value_2_reads_back_as_off():
    """The app cycles light 0->1->2->0 but only one state bit exists."""
    assert decode_state(AFTER_LIGHT_VALUE_2).light is False


def test_swing_on():
    state = decode_state(AFTER_SWING_ON)
    assert state.swing is True
    assert state.light is False


def test_intake_outer():
    assert decode_state(AFTER_INTAKE_OUTER).wind_side == 1


def test_switching_to_celsius_rescales_the_setpoint():
    """The controller converts its own setpoint: 75 degF became 23 degC."""
    state = decode_state(AFTER_UNIT_CELSIUS)
    assert state.is_fahrenheit is False
    assert state.target_temperature == 23
    assert state.inlet_temperature == 22


def test_timer_countdown_is_in_minutes():
    """A one hour timer reported 59, so the field counts minutes."""
    state = decode_state(AFTER_TIMER_1H)
    assert state.setting_timer is True
    assert state.remaining_close_time == 59
    assert state.remaining_open_time == 0


def test_dry_mode_reports_state_value_2():
    state = decode_state(AFTER_MODE_DRY)
    assert state.mode_state is ModeState.DRY
    assert state.mode == 2
    # The unit drops to its lowest fan speed in dry mode.
    assert state.fan_speed == 1


def test_eco_reports_base_mode_zero():
    """ECO clears the base mode field, which is not a valid ModeState.

    The climate entity has to cope with this rather than reporting an unknown
    HVAC mode whenever ECO is engaged.
    """
    state = decode_state(AFTER_PRESET_ECO)
    assert state.eco is True
    assert state.mode == 0
    assert state.mode_state is None
    assert state.power is True


def test_sleep_keeps_the_base_mode():
    state = decode_state(AFTER_PRESET_SLEEP)
    assert state.sleep is True
    assert state.eco is False
    assert state.mode_state is ModeState.COOL


def test_turbo_raises_fan_speed():
    state = decode_state(AFTER_PRESET_TURBO)
    assert state.turbo is True
    assert state.fan_speed == 5
    assert state.mode_state is ModeState.COOL


def test_under_voltage_is_decivolts():
    """Setting 10.0 V put 100 in the frame, confirming the decivolt scale."""
    state = decode_state(AFTER_UVP_10V)
    assert state.under_voltage_decivolts == 100
    assert state.under_voltage == 10.0


def test_presets_are_mutually_exclusive_in_captures():
    """Each preset frame shows exactly one modifier flag set."""
    for frame in (AFTER_PRESET_ECO, AFTER_PRESET_SLEEP, AFTER_PRESET_TURBO):
        state = decode_state(frame)
        assert sum((state.eco, state.sleep, state.turbo, state.auto)) == 1
