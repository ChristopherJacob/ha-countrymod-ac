# ContryMod BLE Home Assistant Integration

## Goal

Create a Home Assistant custom integration for the Bluetooth-enabled 12 V
ContryMod RV air conditioner. Version 1 exposes the controls available in the
official AeroLink Core app: power, target temperature, operating mode, and
recirculation.

## Known device facts

- Controller observed by the RV Home Assistant host: `KT2000000000000`
  (`AA:BB:CC:DD:EE:FF`).
- It is a nearby, unpaired Bluetooth Low Energy peripheral.
- The official app is AeroLink Core. Its Android package is
  `com.kingcontech.btac`.
- Pairing was performed with in-app nearby-device discovery; a QR code is not
  required for the installed controller.

The implementation must not assume that this address is stable. Discovery and
configuration will identify the controller by advertised device identity and
the protocol fingerprint recovered during discovery.

## Delivery scope

The integration will provide:

- a `climate` entity with `off` plus the confirmed operating modes, target
  temperature, and current state when the controller reports it;
- a recirculation `switch` when the recovered protocol exposes it;
- Bluetooth discovery and config flow, including an explicit selected-device
  confirmation;
- connection, notification/polling, and reconnection management; and
- developer documentation and automated tests based on captured BLE fixtures.

Timers, display-light controls, firmware changes, cloud connectivity, and any
controls not present in the app are outside version 1.

## Protocol-discovery strategy

Use a static-first workflow.

1. Obtain and inspect the Android AeroLink Core package for Bluetooth UUIDs,
   command framing, checksums, state decoding, and expected control values.
2. Read the target's GATT services and characteristics from the RV Home
   Assistant host. This phase is read-only except for a connection request.
3. Validate one command at a time against the physical AC, with user-observed
   state changes and raw request/response captures saved as redacted fixtures.
4. Implement only commands that have passed validation.

The RV host's ordinary Bluetooth adapter cannot passively record the iPhone's
BLE connection to the AC. A dedicated radio sniffer is reserved as a fallback
only if app inspection and direct GATT validation cannot recover the protocol.

## Architecture

```
Home Assistant config flow / Bluetooth discovery
                 |
                 v
        ContryMod coordinator
      (connection and refresh lifecycle)
                 |
                 v
         Protocol client / codec
  (GATT UUIDs, frames, parsing, validation)
           |                 |
           v                 v
       Climate entity   Recirculation switch
```

The protocol client owns all raw bytes and BLE characteristic access. It has a
small typed interface such as `read_state`, `set_power`, `set_temperature`,
`set_mode`, and `set_recirculation`. The coordinator serializes commands,
updates a cached immutable state, and informs entities. Platform entities never
construct BLE frames directly.

## State and failures

On startup, the coordinator connects and obtains a complete state snapshot.
It subscribes to notifications when supported; otherwise it polls at a
conservative interval. Commands wait for a protocol acknowledgement or an
observed state update before Home Assistant publishes their result.

Transient BLE failures use bounded reconnect backoff. While disconnected, the
entities are unavailable rather than presenting stale values as current. Invalid
frames, unsupported values, authentication failures, and command timeouts are
reported through Home Assistant diagnostics without logging credentials or
unnecessary raw payloads.

## Testing and acceptance criteria

Unit tests cover frame encoding, decoding, validation, and error paths using
captured request/response fixtures. Coordinator tests use a fake BLE client to
verify reconnect and entity-update behavior. Home Assistant tests verify
config-flow and platform setup.

Acceptance requires that the integration, from a clean Home Assistant setup,
discovers/configures the target and reliably performs each confirmed version-1
operation: power, target temperature, every app-exposed HVAC mode, and
recirculation. It must recover from a disconnect without reconfiguration.

## Security and repository policy

No device-specific pairing material, QR content, Bluetooth captures containing
identifiers, or Home Assistant credentials are committed. Fixtures contain only
the minimally necessary, anonymized frames. The first remote push will be made
to a GitHub repository selected by the user after local development is ready.
