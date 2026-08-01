"""Frame codec for the CountryMod / AeroLink Core BLE air conditioner.

This module owns every raw byte. It has no Home Assistant or Bluetooth
dependency so it can be exercised directly by unit tests.

See docs/protocol-discovery/protocol-contract.md for the evidence behind each
constant here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

HEADER = b"\x5a\x5a"
TRAILER = b"\x0d\x0a"

# 0x5A + 0x5A + 5, the constant part of the checksum.
_CHECKSUM_BASE = 185

# The payload is a single value byte for every command the controller exposes.
PAYLOAD_SIZE = 1

# Kind code. 1 is what the app writes for its own bindings and what the
# controller was validated against.
DEFAULT_KIND_CODE = 1

MIN_FRAME_LEN = 19
STATE_FRAME_LEN = 21

# Longest run of bytes that may be treated as one frame. Observed frames are 21
# bytes; anything materially longer means the leading 5A 5A was noise, not a
# real header, so the reassembler resynchronises past it.
MAX_FRAME_LEN = 64

# Guards a runaway reassembly buffer if the controller ever streams garbage.
MAX_BUFFER = 512


class Command(IntEnum):
    """Command codes written to FFE2."""

    POWER = 1
    WORK_MODE = 2
    TARGET_TEMPERATURE = 3
    FAN_SPEED = 4
    UNDER_VOLTAGE = 5
    SCREEN_DISPLAY = 10
    TIMER_ENABLE = 22
    TIMER_VALUE = 24
    LIGHT = 28
    TEMPERATURE_UNIT = 32
    WIND_SIDE = 68
    SWING = 69
    REFRESH = 0xFF


class Power(IntEnum):
    """Values for Command.POWER."""

    OFF = 1
    ON = 2


class ModeCommand(IntEnum):
    """Values for Command.WORK_MODE (the app's ``Bt`` enum).

    These are NOT the values the controller reports back. See ModeState.
    """

    COOL = 1
    FAN = 2
    ECO = 4
    SLEEP = 5
    TURBO = 6
    DRY = 7
    HEAT = 8
    AUTO = 9


class ModeState(IntEnum):
    """Base mode as reported in the state frame (the app's ``Vt`` enum)."""

    COOL = 1
    DRY = 2
    FAN = 3
    HEAT = 4


#: Reported base mode -> the command value that selects it again.
MODE_STATE_TO_COMMAND: dict[ModeState, ModeCommand] = {
    ModeState.COOL: ModeCommand.COOL,
    ModeState.DRY: ModeCommand.DRY,
    ModeState.FAN: ModeCommand.FAN,
    ModeState.HEAT: ModeCommand.HEAT,
}

MIN_FAN_SPEED = 1
MAX_FAN_SPEED = 6

MIN_TEMP_C = 16
MAX_TEMP_C = 30
MIN_TEMP_F = 61
MAX_TEMP_F = 86


class ProtocolError(ValueError):
    """A frame could not be built or decoded."""


def checksum(payload_size: int, code: int, value: int, kind_code: int) -> int:
    """Return the command checksum byte."""
    return (_CHECKSUM_BASE + payload_size + code + value + kind_code) & 0xFF


def build_command(code: int, value: int, kind_code: int = DEFAULT_KIND_CODE) -> bytes:
    """Build a 9-byte command frame for FFE2."""
    if not 0 <= code <= 0xFF:
        raise ProtocolError(f"command code out of range: {code}")
    if not 0 <= value <= 0xFF:
        raise ProtocolError(f"command value out of range: {value}")
    if not 0 <= kind_code <= 0xFF:
        raise ProtocolError(f"kind code out of range: {kind_code}")
    return bytes(
        (
            0x5A,
            0x5A,
            5 + PAYLOAD_SIZE,
            kind_code,
            code,
            value,
            checksum(PAYLOAD_SIZE, code, value, kind_code),
            0x0D,
            0x0A,
        )
    )


def build_query(
    code: int = Command.REFRESH, kind_code: int = DEFAULT_KIND_CODE
) -> bytes:
    """Build a read-only query frame.

    A value of 0 asks the controller to report state without changing it.
    """
    return build_command(code, 0, kind_code)


def encode_timer_value(hours: int, minute_index: int) -> int:
    """Pack a timer value.

    ``minute_index`` is the app's picker index (0-12 for 0, 5, ... 60 minutes),
    not the displayed minute count.
    """
    if not 0 <= hours <= 0x0F:
        raise ProtocolError(f"timer hours out of range: {hours}")
    if not 0 <= minute_index <= 0x0F:
        raise ProtocolError(f"timer minute index out of range: {minute_index}")
    return ((hours & 0x0F) << 4) | (minute_index & 0x0F)


@dataclass(frozen=True, slots=True)
class CountryModState:
    """Decoded controller state."""

    power: bool
    mode: int
    fan_speed: int
    screen_display: bool
    turbo: bool
    auto: bool
    eco: bool
    sleep: bool
    swing: bool
    negative_ion: bool
    light: bool
    wind_side: int
    inlet_temperature: int
    core_temperature: int
    compressor_current: int
    fan_current: int
    voltage: int
    under_voltage_decivolts: int
    fault_code: int
    setting_timer: bool
    remaining_open_time: int
    remaining_close_time: int
    is_fahrenheit: bool
    target_temperature: int
    raw: bytes

    @property
    def under_voltage(self) -> float:
        """Under-voltage protection setpoint in volts."""
        return self.under_voltage_decivolts / 10

    @property
    def mode_state(self) -> ModeState | None:
        """Base mode as a known enum member, or None if unrecognised."""
        try:
            return ModeState(self.mode)
        except ValueError:
            return None

    @property
    def has_fault(self) -> bool:
        return self.fault_code != 0


def validate_frame(frame: bytes) -> None:
    """Raise ProtocolError if ``frame`` is not a well-formed state frame."""
    if len(frame) < MIN_FRAME_LEN:
        raise ProtocolError(f"frame too short: {len(frame)} bytes")
    if frame[0:2] != HEADER:
        raise ProtocolError(f"bad header: {frame[0:2].hex()}")
    if frame[-2:] != TRAILER:
        raise ProtocolError(f"bad trailer: {frame[-2:].hex()}")
    expected = sum(frame[: len(frame) - 3]) & 0xFF
    actual = frame[len(frame) - 3]
    if expected != actual:
        raise ProtocolError(
            f"bad checksum: expected {expected:#04x}, got {actual:#04x}"
        )


def decode_state(frame: bytes) -> CountryModState:
    """Decode a complete state frame.

    Raises ProtocolError if the frame is malformed.
    """
    validate_frame(frame)
    # Fields live at fixed offsets, so a frame long enough to pass validation
    # can still be too short to carry the target temperature.
    if len(frame) < STATE_FRAME_LEN:
        raise ProtocolError(f"frame carries no target temperature: {len(frame)} bytes")

    status = frame[2]
    flags = frame[3]
    return CountryModState(
        power=bool((status >> 7) & 1),
        mode=(status >> 4) & 0x07,
        fan_speed=(status >> 1) & 0x07,
        screen_display=bool(status & 1),
        turbo=bool((flags >> 7) & 1),
        auto=bool((flags >> 6) & 1),
        eco=bool((flags >> 5) & 1),
        sleep=bool((flags >> 4) & 1),
        swing=bool((flags >> 3) & 1),
        negative_ion=bool((flags >> 2) & 1),
        light=bool((flags >> 1) & 1),
        wind_side=flags & 1,
        inlet_temperature=frame[4],
        core_temperature=frame[5],
        compressor_current=frame[6],
        fan_current=frame[7],
        voltage=frame[8],
        under_voltage_decivolts=frame[9],
        fault_code=frame[10],
        setting_timer=bool(frame[11]),
        remaining_open_time=(frame[12] << 8) | frame[13],
        remaining_close_time=(frame[14] << 8) | frame[15],
        is_fahrenheit=bool(frame[16] & 1),
        target_temperature=frame[17],
        raw=bytes(frame),
    )


class FrameReassembler:
    """Reassembles state frames from fragmented BLE notifications.

    The controller splits each frame across several notifications (10-byte and
    1-byte chunks were observed), so bytes must be buffered and scanned for
    ``5A 5A`` ... ``0D 0A`` delimiters.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def reset(self) -> None:
        self._buffer.clear()

    def add(self, data: bytes) -> list[bytes]:
        """Append notification bytes and return any complete frames."""
        self._buffer.extend(data)

        frames: list[bytes] = []
        while True:
            start = self._buffer.find(HEADER)
            if start < 0:
                # Keep a trailing byte: it may be the first half of a header.
                del self._buffer[: max(0, len(self._buffer) - 1)]
                break
            if start > 0:
                del self._buffer[:start]
            end = self._buffer.find(TRAILER, len(HEADER))
            if end < 0:
                if len(self._buffer) > MAX_FRAME_LEN:
                    # No trailer within a plausible frame length, so this
                    # header is noise. Step past it and rescan.
                    del self._buffer[: len(HEADER)]
                    continue
                break
            frame_len = end + len(TRAILER)
            if frame_len > MAX_FRAME_LEN:
                del self._buffer[: len(HEADER)]
                continue
            frames.append(bytes(self._buffer[:frame_len]))
            del self._buffer[:frame_len]

        if len(self._buffer) > MAX_BUFFER:
            self._buffer.clear()
        return frames

    def add_and_decode(self, data: bytes) -> list[CountryModState]:
        """Append bytes and return decoded state for every valid frame.

        Malformed frames are dropped rather than raising, so one corrupt
        notification cannot stall the stream.
        """
        states: list[CountryModState] = []
        for frame in self.add(data):
            try:
                states.append(decode_state(frame))
            except ProtocolError:
                continue
        return states


def clamp_target_temperature(value: float, is_fahrenheit: bool) -> int:
    """Clamp a requested setpoint to the range the app allows."""
    low, high = (MIN_TEMP_F, MAX_TEMP_F) if is_fahrenheit else (MIN_TEMP_C, MAX_TEMP_C)
    return max(low, min(high, round(value)))
