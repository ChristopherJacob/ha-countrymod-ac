# CountryMod RV Air Conditioner — Home Assistant integration

Local Bluetooth control for the CountryMod 12 V / 24 V RV air conditioner sold
with the *Bluetooth Control Panel Upgrade Kit*, whose phone app is **AeroLink
Core** (`com.kingcontech.btac`).

No cloud, no account, no pairing. Home Assistant talks straight to the display
board over BLE.

## Status

The wire protocol was recovered by decompiling the vendor app and then validated
against a physical unit. Every control this integration exposes has been
confirmed on real hardware, and the integration itself has been driven end to
end from the Home Assistant UI. The one exception is **HEAT**, which the test
unit does not implement — see [Validation status](#validation-status).

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
**Add integration → CountryMod RV Air Conditioner**.

Controllers advertise as `KT` followed by a serial number, e.g.
`KT2026020005224`, and advertise no service UUIDs — so discovery matches on the
name.

Once anything connects to a controller, the host caches the module's GAP name
(`LS Dis Server`) in place of the serial. Discovery accepts both names, but
automatic discovery only fires on the serial. If your controller has been used
with the AeroLink Core app and does not turn up on its own, add it manually, or
clear the stale name first:

```bash
bluetoothctl remove AA:BB:CC:DD:EE:FF
```

## Entities

| Entity | Type | Notes |
| --- | --- | --- |
| Air conditioner | `climate` | Power, mode, target temperature, fan speed, swing, preset |
| Inlet temperature | `sensor` | Return-air temperature, in the unit the controller reports |
| Coil temperature | `sensor` | Diagnostic; Celsius is inferred |
| Supply voltage | `sensor` | Battery voltage seen by the controller |
| Fault / Fault code | `binary_sensor`, `sensor` | Non-zero fault code raises the problem flag |
| Panel display | `switch` | The controller's own screen |
| Light | `switch` | Ambient light; the controller exposes only on/off state |
| Air intake | `select` | Recirculate or fresh air |
| Low voltage cut-off | `number` | Battery protection setpoint |
| Compressor / fan current | `sensor` | Disabled by default; scaling unconfirmed |
| Timer remaining | `sensor` | Minutes; disabled by default |

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

Confirmed against the physical unit, each verified by a returned state frame:

- state refresh and full state decoding
- power on and off
- target temperature, fan speed
- work modes COOL, FAN and DRY
- presets ECO, SLEEP, TURBO and AUTO
- swing, panel display, light, air intake
- low voltage cut-off, temperature unit, timer enable / value / disable

Every one of these has also been exercised from the Home Assistant UI against
the real unit, so the whole path — service call, coordinator, GATT write,
confirming query, decoded state — is known to work, not just the frame format.

**Not** confirmed:

- **HEAT.** The test unit ignored the mode command completely — it appears to
  be a cooling-only model. Other CountryMod units may accept it. The integration
  raises an error rather than silently doing nothing when a unit declines a
  mode, so you will get a clear failure rather than a control that does
  nothing.
- **Negative ion.** The state flag decodes, but the vendor app has no command
  code for it, so there is nothing to send.

Three traps worth knowing about if you talk to one of these units yourself:

- The command and state mode enums are **not** the same. Commanding FAN uses
  value `2`, and the controller then reports mode `3`.
- **ECO clears the base mode field** to `0`, which is not one of the
  controller's own mode values.
- **Changing the temperature unit re-scales the setpoint** on the controller
  itself — 75 °F becomes 23 °C. Do not convert locally.

Still unconfirmed: the scaling of the compressor and fan current fields (both
read zero in every capture, including while actively cooling), and whether the
coil temperature really is Celsius.

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
against a physical unit. Not affiliated with CountryMod or Kingcontech.
