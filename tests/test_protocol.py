"""Tests for the ContryMod frame codec.

Fixtures marked "captured" are verbatim frames recorded from the live
controller on 2026-08-01; see docs/protocol-discovery/command-validation.md.
"""

from __future__ import annotations

import pytest

from custom_components.contrymod_ac.protocol import (
    Command,
    FrameReassembler,
    ModeCommand,
    ModeState,
    Power,
    ProtocolError,
    build_command,
    build_query,
    clamp_target_temperature,
    decode_state,
    encode_timer_value,
)


def h(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


# Captured: power on, COOL, auto, fan 3, 75 degF target, 73 degF inlet, 13 V.
BASELINE = h("5a 5a 97 40 49 16 00 00 0d 5a 00 00 00 00 00 00 01 4b 9d 0d 0a")
# Captured: same, after the setpoint was raised one degree.
TARGET_76 = h("5a 5a 97 40 44 04 00 00 0d 5a 00 00 00 00 00 00 01 4c 87 0d 0a")
# Captured: same baseline conditions, fan speed raised to 4.
FAN_4 = h("5a 5a 99 40 45 11 00 00 0d 5a 00 00 00 00 00 00 01 4b 96 0d 0a")
# Captured: work mode commanded to FAN (command value 2), reported as mode 3.
MODE_FAN = h("5a 5a b7 40 47 15 00 00 0d 5a 00 00 00 00 00 00 01 4b ba 0d 0a")


class TestBuildCommand:
    @pytest.mark.parametrize(
        ("code", "value", "expected"),
        [
            # Every frame below was written to the controller and confirmed to
            # produce the intended state change.
            (Command.REFRESH, 0, "5a 5a 06 01 ff 00 ba 0d 0a"),
            (Command.TARGET_TEMPERATURE, 76, "5a 5a 06 01 03 4c 0a 0d 0a"),
            (Command.TARGET_TEMPERATURE, 75, "5a 5a 06 01 03 4b 09 0d 0a"),
            (Command.FAN_SPEED, 4, "5a 5a 06 01 04 04 c3 0d 0a"),
            (Command.FAN_SPEED, 3, "5a 5a 06 01 04 03 c2 0d 0a"),
            (Command.WORK_MODE, ModeCommand.FAN, "5a 5a 06 01 02 02 bf 0d 0a"),
            (Command.WORK_MODE, ModeCommand.COOL, "5a 5a 06 01 02 01 be 0d 0a"),
        ],
    )
    def test_matches_validated_frames(self, code, value, expected):
        assert build_command(code, value) == h(expected)

    def test_checksum_wraps_at_256(self):
        # 185 + 1 + 255 + 0 + 1 = 442, which must wrap to 0xBA.
        assert build_command(Command.REFRESH, 0)[6] == 0xBA

    def test_checksum_is_sum_of_preceding_bytes(self):
        frame = build_command(Command.TARGET_TEMPERATURE, 30)
        assert frame[6] == sum(frame[:6]) & 0xFF

    def test_query_sends_zero_value(self):
        assert build_query(Command.POWER) == build_command(Command.POWER, 0)

    def test_kind_code_changes_checksum(self):
        assert build_command(Command.POWER, 1, kind_code=2)[6] == (
            build_command(Command.POWER, 1, kind_code=1)[6] + 1
        )

    @pytest.mark.parametrize(
        ("code", "value"), [(0x100, 0), (-1, 0), (1, 256), (1, -1)]
    )
    def test_rejects_out_of_range(self, code, value):
        with pytest.raises(ProtocolError):
            build_command(code, value)

    def test_power_values(self):
        assert build_command(Command.POWER, Power.OFF) == h(
            "5a 5a 06 01 01 01 bd 0d 0a"
        )
        assert build_command(Command.POWER, Power.ON) == h("5a 5a 06 01 01 02 be 0d 0a")


class TestDecodeState:
    def test_decodes_captured_baseline(self):
        state = decode_state(BASELINE)
        assert state.power is True
        assert state.mode == ModeState.COOL
        assert state.fan_speed == 3
        assert state.screen_display is True
        assert state.auto is True
        assert (state.turbo, state.eco, state.sleep, state.swing) == (
            False,
            False,
            False,
            False,
        )
        assert state.inlet_temperature == 73
        assert state.core_temperature == 22
        assert state.voltage == 13
        assert state.under_voltage == 9.0
        assert state.fault_code == 0
        assert state.has_fault is False
        assert state.is_fahrenheit is True
        assert state.target_temperature == 75
        assert state.setting_timer is False

    def test_setpoint_change_is_visible(self):
        assert decode_state(TARGET_76).target_temperature == 76

    def test_fan_speed_change_is_visible(self):
        assert decode_state(FAN_4).fan_speed == 4
        # The rest of the status byte must be unaffected.
        assert decode_state(FAN_4).mode == ModeState.COOL
        assert decode_state(FAN_4).power is True

    def test_fan_mode_reports_state_enum_not_command_enum(self):
        """The controller reports 3 for a mode commanded with value 2."""
        state = decode_state(MODE_FAN)
        assert state.mode == ModeState.FAN
        assert state.mode == 3
        assert ModeCommand.FAN == 2
        assert state.mode_state is ModeState.FAN

    def test_mode_state_is_none_when_unrecognised(self):
        frame = bytearray(BASELINE)
        frame[2] = (frame[2] & 0x8F) | (5 << 4)  # a mode value with no meaning
        frame[18] = sum(frame[:18]) & 0xFF
        assert decode_state(bytes(frame)).mode_state is None

    def test_rejects_bad_header(self):
        frame = bytearray(BASELINE)
        frame[0] = 0x5B
        with pytest.raises(ProtocolError, match="header"):
            decode_state(bytes(frame))

    def test_rejects_bad_trailer(self):
        frame = bytearray(BASELINE)
        frame[-1] = 0x0B
        with pytest.raises(ProtocolError, match="trailer"):
            decode_state(bytes(frame))

    def test_rejects_bad_checksum(self):
        frame = bytearray(BASELINE)
        frame[18] ^= 0xFF
        with pytest.raises(ProtocolError, match="checksum"):
            decode_state(bytes(frame))

    def test_rejects_short_frame(self):
        with pytest.raises(ProtocolError, match="too short"):
            decode_state(h("5a 5a 97 40 0d 0a"))

    def test_rejects_frame_without_target_temperature(self):
        """A 19-byte frame passes validation but cannot carry byte 17."""
        body = bytearray(h("5a 5a 97 40 49 16 00 00 0d 5a 00 00 00 00 00 00"))
        frame = body + bytes([sum(body) & 0xFF]) + b"\x0d\x0a"
        assert len(frame) == 19
        with pytest.raises(ProtocolError, match="target temperature"):
            decode_state(bytes(frame))

    def test_celsius_flag(self):
        frame = bytearray(BASELINE)
        frame[16] = 0
        frame[18] = sum(frame[:18]) & 0xFF
        assert decode_state(bytes(frame)).is_fahrenheit is False

    def test_power_off_and_flags(self):
        frame = bytearray(BASELINE)
        frame[2] &= 0x7F  # clear power
        frame[3] = 0xFF  # every modifier flag set
        frame[18] = sum(frame[:18]) & 0xFF
        state = decode_state(bytes(frame))
        assert state.power is False
        assert all(
            (
                state.turbo,
                state.auto,
                state.eco,
                state.sleep,
                state.swing,
                state.negative_ion,
                state.light,
            )
        )
        assert state.wind_side == 1

    def test_timer_and_fault_fields(self):
        frame = bytearray(BASELINE)
        frame[10] = 7  # fault code
        frame[11] = 1  # timer enabled
        frame[12], frame[13] = 0x01, 0x2C  # 300
        frame[14], frame[15] = 0x00, 0x1E  # 30
        frame[18] = sum(frame[:18]) & 0xFF
        state = decode_state(bytes(frame))
        assert state.fault_code == 7
        assert state.has_fault is True
        assert state.setting_timer is True
        assert state.remaining_open_time == 300
        assert state.remaining_close_time == 30


class TestFrameReassembler:
    def test_reassembles_observed_fragmentation(self):
        """The controller splits frames into 10-byte and 1-byte chunks."""
        reassembler = FrameReassembler()
        assert reassembler.add_and_decode(BASELINE[:10]) == []
        assert reassembler.add_and_decode(BASELINE[10:20]) == []
        states = reassembler.add_and_decode(BASELINE[20:])
        assert len(states) == 1
        assert states[0].target_temperature == 75

    def test_byte_at_a_time(self):
        reassembler = FrameReassembler()
        states: list = []
        for byte in BASELINE:
            states.extend(reassembler.add_and_decode(bytes([byte])))
        assert len(states) == 1

    def test_multiple_frames_in_one_notification(self):
        reassembler = FrameReassembler()
        states = reassembler.add_and_decode(BASELINE + TARGET_76)
        assert [s.target_temperature for s in states] == [75, 76]

    def test_discards_leading_garbage(self):
        reassembler = FrameReassembler()
        states = reassembler.add_and_decode(b"\x00\xff\x13" + BASELINE)
        assert len(states) == 1

    def test_corrupt_frame_does_not_stall_stream(self):
        reassembler = FrameReassembler()
        corrupt = bytearray(BASELINE)
        corrupt[18] ^= 0xFF
        assert reassembler.add_and_decode(bytes(corrupt)) == []
        states = reassembler.add_and_decode(BASELINE)
        assert len(states) == 1

    def test_resynchronises_past_a_spurious_header(self):
        """Noise containing 5A 5A must not swallow the frame that follows."""
        reassembler = FrameReassembler()
        noise = b"\x5a\x5a" + b"\x00" * 200
        states = reassembler.add_and_decode(noise + BASELINE)
        assert len(states) == 1
        assert states[0].target_temperature == 75

    def test_buffer_does_not_grow_without_bound(self):
        reassembler = FrameReassembler()
        for _ in range(100):
            reassembler.add(b"\x5a\x5a" + b"\x00" * 100)
        # Still able to decode a good frame afterwards.
        assert len(reassembler.add_and_decode(BASELINE)) == 1

    def test_header_split_across_notifications(self):
        reassembler = FrameReassembler()
        reassembler.add_and_decode(b"\x5a")
        states = reassembler.add_and_decode(BASELINE[1:])
        assert len(states) == 1

    def test_reset_clears_partial_frame(self):
        reassembler = FrameReassembler()
        reassembler.add(BASELINE[:10])
        reassembler.reset()
        assert reassembler.add_and_decode(BASELINE[10:]) == []


class TestHelpers:
    @pytest.mark.parametrize(
        ("value", "fahrenheit", "expected"),
        [
            (75, True, 75),
            (200, True, 86),
            (0, True, 61),
            (22, False, 22),
            (99, False, 30),
            (-5, False, 16),
            (75.4, True, 75),
            (75.6, True, 76),
        ],
    )
    def test_clamp_target_temperature(self, value, fahrenheit, expected):
        assert clamp_target_temperature(value, fahrenheit) == expected

    def test_encode_timer_value(self):
        assert encode_timer_value(2, 6) == 0x26
        assert encode_timer_value(0, 0) == 0x00

    @pytest.mark.parametrize(("hours", "minutes"), [(16, 0), (0, 16), (-1, 0)])
    def test_encode_timer_value_rejects_out_of_range(self, hours, minutes):
        with pytest.raises(ProtocolError):
            encode_timer_value(hours, minutes)
