# ContryMod RV Air Conditioner — Home Assistant integration

Local Bluetooth control for the ContryMod 12 V / 24 V RV air conditioner sold
with the *Bluetooth Control Panel Upgrade Kit*, whose phone app is **AeroLink
Core** (`com.kingcontech.btac`).

No cloud, no account, no pairing. Home Assistant talks straight to the display
board over BLE.

## Status

The wire protocol was recovered by decompiling the vendor app and then
validated against a physical unit. Setpoint, fan speed, mode switching, and
state decoding are confirmed on real hardware; the rest is implemented from the
app's own code but has not been exercised on a unit. See
[Validation status](#validation-status) before trusting a control in an
automation.

## Requirements

- Home Assistant with a working Bluetooth adapter in range of the AC
  (the ESPHome Bluetooth proxy also works).
- The air conditioner powered on. The display board only answers while the unit
  has power.

## Installation

Copy `custom_components/contrymod_ac` into your Home Assistant `config`
directory:

```
<config>/custom_components/contrymod_ac/
```

Restart Home Assistant. The controller is discovered automatically — look for a
notification under **Settings → Devices & services**, or add it manually with
**Add integration → ContryMod RV Air Conditioner**.

Controllers advertise as `KT` followed by a serial number, e.g.
`KT2026020005224`.

## Entities

| Entity | Type | Notes |
| --- | --- | --- |
| Air conditioner | `climate` | Power, mode, target temperature, fan speed, swing, preset |
| Inlet temperature | `sensor` | Return-air temperature, in the unit the controller reports |
| Coil temperature | `sensor` | Diagnostic; Celsius is inferred |
| Supply voltage | `sensor` | Battery voltage seen by the controller |
| Fault / Fault code | `binary_sensor`, `sensor` | Non-zero fault code raises the problem flag |
| Panel display | `switch` | The controller's own screen |
| Air intake | `select` | Recirculate or fresh air |
| Low voltage cut-off | `number` | Battery protection setpoint |
| Compressor / fan current | `sensor` | Disabled by default; scaling unconfirmed |
| Timer remaining | `sensor` | Disabled by default |

The climate entity reports temperatures in whichever unit the controller itself
is set to, and its allowed range follows suit (16–30 °C or 61–86 °F).

`preset_mode` carries the modifiers the unit layers on top of a base mode:
`auto`, `eco`, `sleep`, `turbo`, or `none`.

## How it works

The display board exposes a serial-bridge GATT service: write commands to
`FFE2`, receive state notifications on `FFE1`. Every exchange is a fixed 9-byte
command frame; writing a value of `0` is a read.

The controller never volunteers state — it answers one query with one state
frame — so the coordinator polls, and each command is followed by a fresh query
so Home Assistant shows what the unit actually did rather than what was asked.
Notifications arrive fragmented and are reassembled before decoding.

Full details, including the byte layout and the evidence for each field, are in
[`docs/protocol-discovery/protocol-contract.md`](docs/protocol-discovery/protocol-contract.md).

## Validation status

Confirmed against the physical unit, each verified by a state frame and then
restored to its original value:

- state refresh and full state decoding
- target temperature
- fan speed
- work mode COOL and FAN

Implemented from the vendor app but **not** exercised on hardware: power on/off,
HEAT / DRY / TURBO / ECO / SLEEP / AUTO, swing, panel display, air intake, low
voltage cut-off, and the timer. These are built from the same frame format that
was validated, so they are likely correct, but nobody has watched the unit obey
them.

One trap worth knowing about: the command and state mode enums are **not** the
same. Commanding FAN uses value `2`, and the controller then reports mode `3`.
The integration handles this; anything else talking to the unit needs to.

Also unconfirmed: the scaling of the compressor and fan current fields (both
read zero in every capture), and whether the coil temperature really is
Celsius.

## A note on the phone app

The display board serves one BLE connection at a time. While Home Assistant is
connected, AeroLink Core will not be able to reach the unit, and vice versa.
Remove or disable the integration if you need the app back.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install homeassistant pytest-homeassistant-custom-component ruff
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests
```

The codec in `custom_components/contrymod_ac/protocol.py` has no Home Assistant
or Bluetooth dependency and is tested against frames captured verbatim from the
real controller.

## Credits

Protocol recovered by static analysis of AeroLink Core 1.0.0 and validated
against a physical unit. Not affiliated with ContryMod or Kingcontech.
