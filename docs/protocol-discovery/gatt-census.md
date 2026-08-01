# CountryMod GATT census

Captured from the RV host on 2026-07-30 (UTC), including a later successful
read-only retry. Raw controller transcripts are stored locally in the ignored
`artifacts/ble-captures/` directory; they are not part of this commit.

## Read-only boundary

This was a read-only controller census. The only target interaction was a
temporary `connect`, followed by a `disconnect`. No GATT characteristic write,
pair, trust, remove, block, unblock, controller-configuration, or phone-app
operation was performed. The connection did not remain established.

## Advertisement and pre-connect state

| Field | Controller observation |
| --- | --- |
| Device address | `AA:BB:CC:DD:EE:FF` (the real address is redacted throughout) |
| Address type | `public` |
| Advertised name | The controller record showed `KT2000000000000` in the fresh retry pre-connect snapshot, then `LS Dis Server` while connected and in the post-disconnect snapshot. |
| RSSI | `-64 dBm` in the fresh retry pre-connect snapshot and `-79 dBm` in the post-disconnect snapshot. |
| Advertising flags | `06` |
| First pre-connect state | `Paired: no`, `Bonded: no`, `Trusted: no`, `Blocked: no`, `Connected: no`; LE paired, bonded, and connected were also `no`. |
| Final state | `Connected: no` in the post-disconnect verification. |

The post-disconnect controller record listed
`0000ffe0-0000-1000-8000-00805f9b34fb` as an unknown device UUID. This is
advertisement/controller metadata, distinct from the resolved GATT service
below.

## Connection and enumeration result

An earlier connection attempt ended with:

```
Failed to connect: org.bluez.Error.Failed le-connection-abort-by-local
```

This failure is not attributed to a specific cause by this census. A later
read-only retry first confirmed the target in the controller record, then
reported `Connection successful` and `ServicesResolved: yes`. `menu gatt` and
`list-attributes` returned the target objects below. An explicit `disconnect`
was issued, and the subsequent `bluetoothctl info` verification reported
`Connected: no`.

All object paths below preserve the RV host path. The device address is
replaced with a placeholder, `AA:BB:CC:DD:EE:FF`, so no controller identifier is
published.

## Discovered attributes

`list-attributes` did not emit object properties/flags. “Unavailable” in the
properties column therefore means unavailable in the RV host output, not an
assertion about the peripheral. No value read, characteristic write, or
notification operation was used to obtain the census.

| Type | Handle | Path (device segment redacted) | UUID | Host label / descriptor relation | Properties |
| --- | --- | --- | --- | --- | --- |
| Primary service | `0x0001` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0001` | `00001800-0000-1000-8000-00805f9b34fb` | Generic Access Profile | Unavailable in `list-attributes` output |
| Characteristic | `0x0002` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0001/char0002` | `00002a00-0000-1000-8000-00805f9b34fb` | Device Name | Unavailable in `list-attributes` output |
| Characteristic | `0x0004` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0001/char0004` | `00002a01-0000-1000-8000-00805f9b34fb` | Appearance | Unavailable in `list-attributes` output |
| Primary service | `0x0006` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0006` | `00001801-0000-1000-8000-00805f9b34fb` | Generic Attribute Profile | Unavailable in `list-attributes` output |
| Characteristic | `0x0007` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0006/char0007` | `00002a05-0000-1000-8000-00805f9b34fb` | Service Changed | Unavailable in `list-attributes` output |
| Descriptor | `0x0009` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0006/char0007/desc0009` | `00002902-0000-1000-8000-00805f9b34fb` | Client Characteristic Configuration for `0x0007` | Unavailable in `list-attributes` output |
| Characteristic | `0x000a` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0006/char000a` | `00002b29-0000-1000-8000-00805f9b34fb` | Client Supported Features | Unavailable in `list-attributes` output |
| Characteristic | `0x000c` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service0006/char000c` | `00002b2a-0000-1000-8000-00805f9b34fb` | Database Hash | Unavailable in `list-attributes` output |
| Primary service | `0x000e` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service000e` | `0000ffe0-0000-1000-8000-00805f9b34fb` | Unknown | Unavailable in `list-attributes` output |
| Characteristic | `0x000f` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service000e/char000f` | `0000ffe2-0000-1000-8000-00805f9b34fb` | Unknown | Unavailable in `list-attributes` output |
| Characteristic | `0x0011` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service000e/char0011` | `0000ffe1-0000-1000-8000-00805f9b34fb` | Unknown | Unavailable in `list-attributes` output |
| Descriptor | `0x0013` | `/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/service000e/char0011/desc0013` | `00002902-0000-1000-8000-00805f9b34fb` | Client Characteristic Configuration for `0x0011` | Unavailable in `list-attributes` output |

## Static-analysis cross-check

| Static expectation | Expected UUID / role | Status in captured target output | Observed handle | Observed properties |
| --- | --- | --- | --- | --- |
| Custom service | `FFE0` / service | **Present** | `0x000e` | Unavailable in `list-attributes` output |
| Notification characteristic | `FFE1` / notification | **Present**; CCCD descriptor at `0x0013` | `0x0011` | Unavailable in `list-attributes` output |
| Command characteristic | `FFE2` / static write role | **Present** | `0x000f` | Unavailable in `list-attributes` output |

There is no observed UUID mismatch: the successful resolved database contains
all three static expectations at the handles above. The controller did not emit
properties, so the static notification/write role expectations are not verified
as observed properties by this census.

## Commands used

- `bluetoothctl info <redacted target>` before the retry connection attempt
- Interactive `bluetoothctl`: `connect <redacted target>`, `menu gatt`,
  `list-attributes <redacted target>`, `back`, `disconnect <redacted target>`,
  `quit`
- `bluetoothctl info <redacted target>` after disconnection to verify final state

No GATT read, characteristic write, notification subscription, pairing,
trust-setting, removal, or controller configuration command was issued.
