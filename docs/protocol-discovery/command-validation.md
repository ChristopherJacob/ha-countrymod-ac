# ContryMod BLE command validation

Physical validation performed 2026-08-01 (UTC) from the RV Home Assistant host
against the live controller. Raw transcripts are stored locally under the
ignored `artifacts/ble-captures/` directory.

## Why earlier validation attempts appeared to fail

Sessions on 2026-07-30 and 2026-07-31 concluded that the controller never
emitted a notification and that commands had no effect. Both conclusions were
wrong, and the cause was tooling, not the device:

- **`bluetoothctl` does not print notification payloads.** It prints
  `[CHG] Attribute ... Notifying: yes` when the subscription succeeds, and then
  prints nothing for the values that arrive. Every probe driven through
  `bluetoothctl` therefore looked silent. Watching the same characteristic with
  `dbus-monitor` on `org.freedesktop.DBus.Properties.PropertiesChanged`
  immediately showed a steady stream of payloads.
- **The controller answers a query with one state frame.** It does not
  broadcast unprompted. A passive 40-second subscription with no write produced
  nothing, which is correct behaviour, not a fault.
- **No activation, pairing, bonding, or cloud authorisation is required.** The
  successful captures below never sent the `C=0x42` activation frame. The
  controller responds to a plain query on an unpaired, unbonded connection.

The one genuine earlier observation — that a power-off frame produced no
physical change — was never confirmed against a state frame, so it cannot be
distinguished from a mis-parsed write. Power was not re-tested in this session
(see *Not validated* below).

## Method

Each run used one connection: connect, `StartNotify` on FFE1, write frames to
FFE2 as Write Command (`write-without-response`), and record every
`PropertiesChanged` payload with its timestamp. Notification payloads arrive
**fragmented** — observed as 10-byte and 1-byte chunks — and must be
reassembled into `5A 5A ... 0D 0A` frames before decoding.

A command was marked `pass` only when a decoded state frame showed the intended
field change. Every run restored the controller to its baseline value.

## Results

| # | Action | Frame sent (hex) | Observed state change | Result |
| --- | --- | --- | --- | --- |
| 0 | Query state (`C=0xFF`) | `5A 5A 06 01 FF 00 BA 0D 0A` | One complete state frame returned per query, 1:1 | **pass** |
| 1 | Query state (per-field, `C=3`) | `5A 5A 06 01 03 00 BE 0D 0A` | One complete state frame returned per query | **pass** |
| 2 | Target temperature → 76 °F | `5A 5A 06 01 03 4C 0A 0D 0A` | `target_temperature` 75 → 76 | **pass** |
| 3 | Target temperature → 75 °F (restore) | `5A 5A 06 01 03 4B 09 0D 0A` | `target_temperature` 76 → 75 | **pass** |
| 4 | Fan speed → 4 | `5A 5A 06 01 04 04 C3 0D 0A` | `fan_speed` 3 → 4, `byte[2]` `0x97` → `0x99` | **pass** |
| 5 | Fan speed → 3 (restore) | `5A 5A 06 01 04 03 C2 0D 0A` | `fan_speed` 4 → 3 | **pass** |
| 6 | Work mode → FAN (command value 2) | `5A 5A 06 01 02 02 BF 0D 0A` | state `mode` 1 → **3**, `byte[2]` `0x97` → `0xB7` | **pass** |
| 7 | Work mode → COOL (command value 1, restore) | `5A 5A 06 01 02 01 BE 0D 0A` | state `mode` 3 → 1, `byte[2]` back to `0x97` | **pass** |

Baseline before and after every run: `5A 5A 97 40 ... 01 4B <chk> 0D 0A` —
power on, mode COOL, auto flag set, fan speed 3, target 75 °F, unit Fahrenheit,
no fault. The controller was left in exactly this state.

## Confirmed send/receive mode asymmetry

Sequence 6 is the important result. The command value for FAN is `2`, but the
controller then *reports* mode `3`. The two directions use different enums, and
an integration that assumes symmetry will mis-render the mode.

- **Command values** (`C=2`, app enum `Bt`): COOL=1, FAN=2, ECO=4, SLEEP=5,
  TURBO=6, DRY=7, HEAT=8, AUTO=9.
- **State values** (`byte[2]` bits 6–4, app enum `Vt`): COOL=1, DRY=2, FAN=3,
  HEAT=4.

Only the COOL↔COOL and FAN command→state pairs were exercised physically. DRY
and HEAT state values are taken from the app's `Vt` enum and its `workMode`
comparisons, and are not physically confirmed.

## Sample decoded state frame

`5A 5A 97 40 49 16 00 00 0D 5A 00 00 00 00 00 00 01 4B 9D 0D 0A`

| Field | Value |
| --- | --- |
| power | 1 (on) |
| mode | 1 (COOL) |
| fan_speed | 3 |
| screen_display | 1 |
| auto | 1 |
| turbo / eco / sleep / swing / negative_ion / light / wind_side | 0 |
| inlet_temperature | 73 |
| core_temperature | 22 |
| compressor_current | 0 |
| fan_current | 0 |
| voltage | 13 |
| under_voltage | 90 (9.0 V) |
| fault_code | 0 |
| setting_timer | 0 |
| remaining_open_time | 0 |
| remaining_close_time | 0 |
| temperature_unit | 1 (Fahrenheit) |
| target_temperature | 75 |

## Not validated

These remain statically recovered only and were deliberately not exercised,
because each has a disruptive or unattended-unsafe physical effect, or could not
be confirmed from a state frame:

- **Power on/off** (`C=1`, V=1 off / V=2 on).
- **HEAT, DRY, TURBO, ECO, SLEEP, AUTO** mode commands.
- Swing, light, screen display, negative ion, wind side, timer enable/value,
  temperature unit change, and under-voltage setpoint writes.
- Scaling of `compressor_current` and `fan_current`; both read `0` throughout.
- Whether `core_temperature` is Celsius. Its observed range (4–22 while the unit
  reported Fahrenheit elsewhere) makes Celsius by far the most plausible
  reading, but this is inference.

Validating these requires a person at the vehicle to observe the unit and to
abort if it behaves unexpectedly.
