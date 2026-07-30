# ContryMod GATT census

Captured from the RV host on 2026-07-30 (UTC). The raw controller transcript is
stored locally in the ignored `artifacts/ble-captures/` directory; it is not part
of this commit.

## Read-only boundary

This was a read-only controller census. The only target interaction was a
temporary `connect`, followed by a `disconnect`. No GATT characteristic write,
pair, trust, remove, block, unblock, controller-configuration, or phone-app
operation was performed. The connection did not remain established.

## Advertisement and pre-connect state

| Field | Controller observation |
| --- | --- |
| Device address | `CA:04:59:8E:**:**` (redacted after the first four octets) |
| Address type | `public` |
| Advertised name | `KT2026020005224` in the final controller info query. The first required pre-connect query instead showed `LS Dis Server`; the host later refreshed the same device record to `KT2026020005224`. |
| RSSI | `-64 dBm` in the first pre-connect query; `-65 dBm` after the attempt (the live session also reported target updates between `-62` and `-80 dBm`). |
| Advertising flags | `06` |
| First pre-connect state | `Paired: no`, `Bonded: no`, `Trusted: no`, `Blocked: no`, `Connected: no`; LE paired, bonded, and connected were also `no`. |
| Final state | `Connected: no`; the explicit `disconnect` reported success. |

The first pre-connect query listed `0000ffe0-0000-1000-8000-00805f9b34fb`
as an unknown device UUID. This is advertisement/controller metadata, not a
resolved GATT service object.

## Connection and enumeration result

`bluetoothctl` reported a brief target `Connected: yes` transition, then:

```
Failed to connect: org.bluez.Error.Failed le-connection-abort-by-local
```

The target returned to `Connected: no`; no `ServicesResolved: yes` event was
reported for it. `menu gatt` was available, but
`list-attributes CA:04:59:8E:**:**` emitted no target attributes. Therefore no
target service, characteristic, or descriptor path was discovered, and no
target handle or property is available in the host output.

An earlier no-delay command sequence did print GATT objects below a different
cached device path (`.../dev_6C_79_B8_B4_4F_C0/...`) before a target connection
had been confirmed. Those objects are excluded from this census.

## Discovered attributes

None for the target. Because service resolution failed, there are no observed
target paths, handles, UUID-bearing GATT objects, properties, or descriptors to
record. “Unavailable” below means unavailable in the RV host output, not an
assertion that the peripheral lacks the item.

## Static-analysis cross-check

| Static expectation | Expected UUID / role | Status in captured target output | Observed handle | Observed properties |
| --- | --- | --- | --- | --- |
| Custom service | `FFE0` / service | **Present** as an unknown pre-connect device UUID; not GATT-resolved | Unavailable in host output | Unavailable in host output |
| Notification characteristic | `FFE1` / notification | **Absent from the captured target output**; enumeration failed, so this is not evidence of peripheral absence | Unavailable in host output | Unavailable in host output |
| Command characteristic | `FFE2` / static write role | **Absent from the captured target output**; enumeration failed, so this is not evidence of peripheral absence | Unavailable in host output | Unavailable in host output |

There is no observed UUID mismatch: the only expected UUID present in the target
record was `FFE0`. `FFE1` and `FFE2` could not be checked against a resolved
GATT database because the connection was aborted before services resolved.

## Commands used

- `bluetoothctl info <redacted target>` before the connection attempt
- Interactive `bluetoothctl`: `connect <redacted target>`, `menu gatt`,
  `list-attributes <redacted target>`, `back`, `disconnect <redacted target>`,
  `quit`
- `bluetoothctl info <redacted target>` after disconnection

No GATT read, characteristic write, notification subscription, pairing,
trust-setting, removal, or controller configuration command was issued.
