# CountryMod BLE command validation

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
distinguished from a mis-parsed write. Power was later validated through the
integration and works correctly, which supports the mis-parsed-write reading.

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

## Second validation round (2026-08-01)

The remaining controls were exercised the same way. Baseline was restored after
each group, and the controller finished in exactly its starting state.

| Action | Frame sent (hex) | Observed state change | Result |
| --- | --- | --- | --- |
| Panel display off | `5A 5A 06 01 0A 01 C6 0D 0A` | `screen_display` 1 → 0 | **pass** |
| Panel display on | `5A 5A 06 01 0A 02 C7 0D 0A` | `screen_display` 0 → 1 | **pass** |
| Light value 1 | `5A 5A 06 01 1C 01 D8 0D 0A` | `light` 0 → 1 | **pass** |
| Light value 2 | `5A 5A 06 01 1C 02 D9 0D 0A` | `light` 1 → **0** | **pass** (see below) |
| Swing on | `5A 5A 06 01 45 01 01 0D 0A` | `swing` 0 → 1 | **pass** |
| Swing off | `5A 5A 06 01 45 00 00 0D 0A` | `swing` 1 → 0 | **pass** |
| Intake outer | `5A 5A 06 01 44 01 00 0D 0A` | `wind_side` 0 → 1 | **pass** |
| Intake inner | `5A 5A 06 01 44 00 FF 0D 0A` | `wind_side` 1 → 0 | **pass** |
| Under-voltage 10.0 V | `5A 5A 06 01 05 64 24 0D 0A` | `under_voltage` 90 → 100 | **pass** |
| Under-voltage 9.0 V | `5A 5A 06 01 05 5A 1A 0D 0A` | `under_voltage` 100 → 90 | **pass** |
| Unit → Celsius | `5A 5A 06 01 20 01 DC 0D 0A` | `temperature_unit` 1 → 0, `target_temperature` 75 → **23** | **pass** |
| Unit → Fahrenheit | `5A 5A 06 01 20 02 DD 0D 0A` | `temperature_unit` 0 → 1, `target_temperature` 23 → 75 | **pass** |
| Timer enable | `5A 5A 06 01 16 02 D3 0D 0A` | `setting_timer` 0 → 1 | **pass** |
| Timer value 1 h | `5A 5A 06 01 18 10 E3 0D 0A` | `remaining_close_time` 0 → **59** | **pass** |
| Timer disable | `5A 5A 06 01 16 03 D4 0D 0A` | `setting_timer` 1 → 0, countdown → 0 | **pass** |
| Mode DRY | `5A 5A 06 01 02 07 C4 0D 0A` | state `mode` 1 → **2**, `fan_speed` → 1 | **pass** |
| Mode HEAT | `5A 5A 06 01 02 08 C5 0D 0A` | **no state change at all** | **not accepted** |
| Preset ECO | `5A 5A 06 01 02 04 C1 0D 0A` | `eco` 0 → 1, `auto` 1 → 0, `mode` 1 → **0** | **pass** |
| Preset SLEEP | `5A 5A 06 01 02 05 C2 0D 0A` | `sleep` 0 → 1, `mode` back to 1 | **pass** |
| Preset TURBO | `5A 5A 06 01 02 06 C3 0D 0A` | `turbo` 0 → 1, `fan_speed` 1 → 5 | **pass** |
| Preset AUTO | `5A 5A 06 01 02 09 C6 0D 0A` | `auto` 0 → 1, `turbo` → 0 | **pass** |

### Findings that change how the protocol must be read

- **HEAT is not accepted by this unit.** `C=2, V=8` produced no state change
  whatsoever, where every other mode command changed state within one poll.
  This appears to be a cooling-only model. The frame itself is well formed and
  the same code path works for COOL, FAN, and DRY, so this is the unit
  declining the mode rather than a malformed command. Other CountryMod models
  may well accept it.
- **ECO clears the base mode field.** While ECO is engaged, `byte[2]` bits 6–4
  read `0`, which is not one of the controller's own mode values. SLEEP, TURBO
  and AUTO all leave the base mode intact. Any decoder that maps the base mode
  strictly will produce an unknown mode whenever ECO is selected.
- **Timer countdowns are minutes, not seconds.** A one-hour timer reported
  `59`. This matches the app, which renders the field as `hours = value / 60`,
  `minutes = value % 60`.
- **Changing the temperature unit re-scales the setpoint.** The controller did
  the conversion itself: 75 °F became 23 °C, and switching back restored 75 °F.
  A client does not need to convert.
- **Light has three command values but only one state bit.** Value 1 sets the
  bit; value 2 clears it; value 0 leaves it clear. It is a switch, not a level.
- **DRY forces the fan to speed 1**, and TURBO raised it to 5. Fan speed is a
  side effect of some mode changes, so it should be re-read after one.

## Third round: power, through the integration (2026-08-01)

Power was the one control deliberately left for a supervised run, because
cycling a compressor unattended risks short-cycling it. It was exercised from
the Home Assistant climate card with the operator at the vehicle, and is
recorded here from Home Assistant's own state history rather than from a BLE
capture.

| Time | Action | Observed |
| --- | --- | --- |
| 10:44:31 | Panel display off, then on | `switch` followed within one poll |
| 10:44:35 | Light on, then off | `switch` followed within one poll |
| 10:44:46 | **Power off** (`C=1, V=1`) | `climate` → `off` |
| 10:48:03 | **Power on** (`C=1, V=2`) | `climate` → `cool`, 3 min 17 s later |
| 10:48:04 | — | unit came back reporting the `auto` modifier |

Power on/off therefore behaves exactly as the static analysis predicted, and
the whole command path — Home Assistant service call, coordinator, FFE2 write,
confirming query, decoded state frame — is confirmed on real hardware.

## Confirmed send/receive mode asymmetry

Sequence 6 is the important result. The command value for FAN is `2`, but the
controller then *reports* mode `3`. The two directions use different enums, and
an integration that assumes symmetry will mis-render the mode.

- **Command values** (`C=2`, app enum `Bt`): COOL=1, FAN=2, ECO=4, SLEEP=5,
  TURBO=6, DRY=7, HEAT=8, AUTO=9.
- **State values** (`byte[2]` bits 6–4, app enum `Vt`): COOL=1, DRY=2, FAN=3,
  HEAT=4.

COOL, FAN and DRY were all exercised physically, and each reported back the
`Vt` value rather than the value that was sent. Only HEAT remains unconfirmed,
because this unit declined the mode entirely; its state value `4` comes from the
app's `Vt` enum and its `workMode` comparisons.

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

## Still not validated

- **Negative ion.** The state frame decodes the flag (`byte[3]` bit 2), but no
  command code for it was found in the app, so there is nothing to send.
- **HEAT on a unit that supports heating.** This unit declined it.
- Scaling of `compressor_current` and `fan_current`; both read `0` throughout,
  including while the unit was actively cooling.
- Whether `core_temperature` is Celsius. Its observed range (4–22 while the
  unit reported Fahrenheit elsewhere) makes Celsius by far the most plausible
  reading, but this is inference.
