# ContryMod BLE protocol contract

This is the protocol authority for the Home Assistant integration. Every entry
is either physically validated (see `command-validation.md`) or marked as
statically recovered from the AeroLink Core app (see
`aerolink-core-artifact.md`). Nothing here is a guess.

## Device fingerprint

| Property | Value |
| --- | --- |
| Advertised name | `KT` + serial, e.g. `KT2026020005224` |
| GAP device name (after connect) | `LS Dis Server` |
| Address type | public |
| Advertised service UUID | `0000FFE0-0000-1000-8000-00805F9B34FB` |
| Pairing / bonding | Not required, not used |
| Encryption / authentication | None present in the app or on the wire |

Discovery should match the advertised `FFE0` service UUID and then require the
advertised local name to start with `KT`. `FFE0` alone is a generic
serial-bridge UUID shared by many unrelated devices.

## GATT

| Role | UUID | Handle | Properties |
| --- | --- | --- | --- |
| Service | `0000FFE0-…` | `0x000E` | primary |
| Write (commands) | `0000FFE2-…` | `0x000F` | `write`, `write-without-response` |
| Notify (state) | `0000FFE1-…` | `0x0011` | `notify` (CCCD at `0x0013`) |

FFE1 is notify-only; it cannot be read. All state arrives through
notifications.

## Connection sequence

1. Connect. No pairing, bonding, or trust.
2. `StartNotify` on FFE1.
3. Write a query frame to FFE2 to request state.

No activation or handshake frame is needed. The app's `C=0x42` activation frame
relates to its own cloud account binding, not to link establishment, and was
never sent in any successful capture.

## Command frame

Fixed 9 bytes, written to FFE2:

```
5A 5A  LEN  KIND  CODE  VALUE  CHK  0D 0A
```

| Byte | Meaning |
| --- | --- |
| 0–1 | Header `5A 5A` |
| 2 | `LEN` = `5 + payload_size`; payload size is always 1, so `LEN = 0x06` |
| 3 | `KIND` = kind code; `1` for app-created bindings and validated here |
| 4 | `CODE` = command code |
| 5 | `VALUE` = command value; `0` means *query* |
| 6 | `CHK` = `(185 + payload_size + CODE + VALUE + KIND) & 0xFF` |
| 7–8 | Trailer `0D 0A` |

`185` is `0x5A + 0x5A + 5`, so the checksum is equivalently the sum of bytes 0–5
modulo 256.

Writing `VALUE = 0` for any code is a read: the controller replies with one
complete state frame and changes nothing. `CODE = 0xFF, VALUE = 0` is the
app's own 3-second refresh poll and is the preferred way to request state.

### Command codes

| Control | `CODE` | Values | Status |
| --- | --- | --- | --- |
| State refresh | `0xFF` | `0` | **validated** |
| Power | `1` | `1` = off, `2` = on | static only |
| Work mode | `2` | COOL=1, FAN=2, ECO=4, SLEEP=5, TURBO=6, DRY=7, HEAT=8, AUTO=9 | COOL and FAN **validated**; others static only |
| Target temperature | `3` | 16–30 (°C) or 61–86 (°F), sent as the displayed integer | **validated** (°F) |
| Fan speed | `4` | 1–6 | **validated** |
| Under-voltage setpoint | `5` | `10 × volts` | static only |
| Screen display | `10` (`0x0A`) | `1` = off, `2` = on | static only |
| Timer enable | `22` (`0x16`) | `2` = enable, `3` = disable | static only |
| Timer value | `24` (`0x18`) | `(hours & 0x0F) << 4 | (minute_index & 0x0F)` | static only |
| Light | `28` (`0x1C`) | `0`, `1`, `2` | static only |
| Temperature unit | `32` (`0x20`) | `1` = Celsius, `2` = Fahrenheit | static only |
| Wind side | `68` (`0x44`) | `0` = inner, `1` = outer | static only |
| Swing | `69` (`0x45`) | `0` = off, `1` = on | static only |

The app pauses its poll loop, waits ~300 ms, sends one command, then resumes
polling. The integration follows the same pattern.

## State frame

Notifications are **fragmented** — observed as 10-byte and 1-byte chunks. Bytes
must be buffered and reassembled by scanning for `5A 5A` … `0D 0A` before
decoding. Complete frames observed are 21 bytes.

Validation, in order: length ≥ 19; `byte[0] == byte[1] == 0x5A`; last two bytes
`0D 0A`; `sum(bytes[0 .. len-4]) & 0xFF == bytes[len-3]`.

| Byte | Field |
| --- | --- |
| 2 bit 7 | `power` |
| 2 bits 6–4 | `mode` — COOL=1, DRY=2, FAN=3, HEAT=4 |
| 2 bits 3–1 | `fan_speed` |
| 2 bit 0 | `screen_display` |
| 3 bit 7 | `turbo` |
| 3 bit 6 | `auto` |
| 3 bit 5 | `eco` |
| 3 bit 4 | `sleep` |
| 3 bit 3 | `swing` |
| 3 bit 2 | `negative_ion` |
| 3 bit 1 | `light` |
| 3 bit 0 | `wind_side` |
| 4 | `inlet_temperature` (return air, in the reported unit) |
| 5 | `core_temperature` (coil; Celsius inferred, not confirmed) |
| 6 | `compressor_current` (scaling unconfirmed) |
| 7 | `fan_current` (scaling unconfirmed) |
| 8 | `voltage` (volts) |
| 9 | `under_voltage` (decivolts: `90` = 9.0 V) |
| 10 | `fault_code` (`0` = healthy) |
| 11 | `setting_timer` (non-zero → enabled) |
| 12–13 | `remaining_open_time` (big-endian) |
| 14–15 | `remaining_close_time` (big-endian) |
| 16 bit 0 | `temperature_unit` — `0` = Celsius, `1` = Fahrenheit |
| 17 | `target_temperature` (in the reported unit) |
| 18 | checksum |
| 19–20 | trailer `0D 0A` |

### Mode enums are asymmetric

This is the single most important implementation detail. The value used to
*command* a mode is not the value the controller *reports* for it:

| Mode | Command value (`CODE=2`) | Reported `mode` |
| --- | --- | --- |
| COOL | 1 | 1 |
| DRY | 7 | 2 |
| FAN | 2 | 3 |
| HEAT | 8 | 4 |

COOL and FAN were confirmed physically; DRY and HEAT come from the app's enums.

TURBO, ECO, SLEEP and AUTO are *commanded* through the same `CODE=2` but are
*reported* as independent flag bits in byte 3, layered on top of the base mode.
They are modifiers, not base modes.

## Failure semantics

- A frame failing header, trailer, length, or checksum validation is discarded;
  the reassembly buffer resynchronises on the next `5A 5A`.
- A completed write is not evidence of a semantic result. Success is a
  subsequent state frame showing the intended field.
- The controller answers queries only while connected and subscribed; silence
  after a query means the link or subscription is gone, and the connection
  should be torn down and re-established.
