# ContryMod BLE Protocol Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover and validate the AeroLink Core BLE protocol well enough to implement a safe Home Assistant integration for the ContryMod 12 V AC.

**Architecture:** This is the first of two delivery plans. It produces an evidence-backed protocol contract: the controller fingerprint, GATT layout, command frames, and state frames. A later plan will consume that fixed contract to build the custom integration; it must not guess UUIDs or command bytes.

**Tech Stack:** Android APK static analysis (JADX), BlueZ/DBus on the RV Home Assistant host, Bluetooth Low Energy GATT, Markdown evidence records, SHA-256.

---

## File structure

- Create: `.gitignore` — keeps downloaded apps, decompiled sources, and raw captures out of Git.
- Create: `docs/protocol-discovery/aerolink-core-artifact.md` — records app provenance, version, checksum, and static-analysis findings.
- Create: `docs/protocol-discovery/gatt-census.md` — records the target’s observed GATT tree and advertisement identity.
- Create: `docs/protocol-discovery/command-validation.md` — records one reproducible physical result for each control.
- Create: `docs/protocol-discovery/protocol-contract.md` — the sole input to the later Home Assistant implementation plan.
- Local-only, ignored: `artifacts/aerolink-core/` — stores the downloaded APK/AAB and JADX output.
- Local-only, ignored: `artifacts/ble-captures/` — stores raw console/DBus output and any binary captures.

No `custom_components` files are created in this plan. That boundary prevents an integration with undocumented or unvalidated BLE writes.

### Task 1: Prepare an evidence-safe discovery workspace

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Add ignores before downloading any artifacts**

```gitignore
# Python and test caches
__pycache__/
.pytest_cache/

# Reverse-engineering artifacts: potentially contain proprietary code or identifiers
artifacts/
*.apk
*.aab
*.ipa
```

- [ ] **Step 2: Verify sensitive artifact paths are ignored**

Run: `git check-ignore -v artifacts/aerolink-core artifacts/ble-captures sample.apk`

Expected: three lines, each matched by `.gitignore`; no artifact path is eligible for commit.

- [ ] **Step 3: Commit the safe workspace**

```bash
git add .gitignore
git commit -m "chore: prepare BLE discovery workspace"
```

### Task 2: Obtain and inspect the official Android app artifact

**Files:**
- Create: `docs/protocol-discovery/aerolink-core-artifact.md`
- Local-only: `artifacts/aerolink-core/AeroLink-Core.apk`
- Local-only: `artifacts/aerolink-core/jadx/`

- [ ] **Step 1: Obtain the Android app from a traceable source**

Store the unmodified APK at `artifacts/aerolink-core/AeroLink-Core.apk`. Use a source that identifies the package as `com.kingcontech.btac`; do not download a repackaged, modified, or “premium” build. Record the source URL and download time in the artifact record before analysis.

- [ ] **Step 2: Calculate reproducible artifact metadata**

Run:

```bash
shasum -a 256 artifacts/aerolink-core/AeroLink-Core.apk
unzip -p artifacts/aerolink-core/AeroLink-Core.apk AndroidManifest.xml | shasum -a 256
```

Expected: two SHA-256 hashes. Obtain the version name/version code and signing-certificate SHA-256 with Android build tools or APK Analyzer.

- [ ] **Step 3: Write the immutable artifact record from the observed values**

Create `docs/protocol-discovery/aerolink-core-artifact.md` with the official store URL, package identifier, exact download URL, UTC timestamp, APK SHA-256, version name/code, signing-certificate SHA-256, and manifest hash produced in steps 1–2. Do not leave a value blank or substitute a value that was not observed.

- [ ] **Step 4: Decompile without modifying the artifact**

Run:

```bash
jadx --deobf --show-bad-code -d artifacts/aerolink-core/jadx artifacts/aerolink-core/AeroLink-Core.apk
rg -n -i 'BluetoothGatt|BluetoothLeScanner|writeCharacteristic|setCharacteristicNotification|0000[0-9a-f]{4}-0000-1000-8000-00805f9b34fb|UUID|CRC|checksum|AES' artifacts/aerolink-core/jadx
```

Expected: the first command creates readable source under the ignored artifact directory. The second command reports every BLE API use and UUID-like value for manual classification.

- [ ] **Step 5: Trace the four version-1 actions to bytes**

For each action below, trace UI event → application method → frame builder → GATT characteristic write, then record the exact value mapping and source-class path in the static findings table:

| Action | Required values |
| --- | --- |
| Power | off, on |
| Temperature | one complete valid range and encoding unit |
| HVAC mode | every enum shown by the app |
| Recirculation | off, on |

If a frame uses a derived key, nonce, or checksum, record the complete derivation inputs and source-class path; never replace a missing derivation with a guessed byte.

- [ ] **Step 6: Check static-analysis completeness**

Run:

```bash
rg -n -i 'BluetoothGatt|BluetoothLeScanner|writeCharacteristic|setCharacteristicNotification|UUID|CRC|checksum|AES' docs/protocol-discovery/aerolink-core-artifact.md
```

Expected: output that cites each recovered BLE finding, including its JADX source path. The record must explicitly state `not present in inspected artifact` only for a feature whose absence was verified.

- [ ] **Step 7: Commit only the documentation**

```bash
git add docs/protocol-discovery/aerolink-core-artifact.md
git commit -m "docs: record AeroLink Core BLE static analysis"
git status --short
```

Expected: a clean status; the APK and JADX tree remain ignored.

### Task 3: Capture the controller’s read-only GATT census

**Files:**
- Create: `docs/protocol-discovery/gatt-census.md`
- Local-only: `artifacts/ble-captures/gatt-census-<UTC timestamp>.txt`

- [ ] **Step 1: Record the advertisement identity before connecting**

Run from the development workstation:

```bash
ssh va 'bluetoothctl info AA:BB:CC:DD:EE:FF'
```

Expected: `Name: KT2000000000000`, a public address, and no pairing/bonding. Copy the name, address type, RSSI, advertising flags, and observed connection state into the census. Do not run `pair`, `trust`, or `remove`.

- [ ] **Step 2: Connect temporarily and enumerate services/characteristics without writing**

On the RV host, use an interactive `bluetoothctl` session:

```text
connect AA:BB:CC:DD:EE:FF
menu gatt
list-attributes
back
disconnect AA:BB:CC:DD:EE:FF
quit
```

Save the terminal transcript under `artifacts/ble-captures/`. For every discovered attribute, record object path, handle, UUID, properties, and descriptor UUID in the census. If `list-attributes` is unavailable on the host’s BlueZ version, use `org.freedesktop.DBus.ObjectManager.GetManagedObjects` against `org.bluez` while the device is connected and record the same fields.

- [ ] **Step 3: Cross-check the app against the real GATT tree**

In the census, add a table with the service and every candidate read/write/notify characteristic from static analysis. Mark each as `present`, `absent`, or `different UUID`; quote the observed handle/properties for every `present` row.

- [ ] **Step 4: Enforce the read-only boundary**

Run:

```bash
rg -n -i '(^|[^a-z])(write|pair|trust|remove)([^a-z]|$)' docs/protocol-discovery/gatt-census.md
```

Expected: no output. The census document must not claim that any write, pairing, trust, or removal operation occurred.

- [ ] **Step 5: Commit the GATT census**

```bash
git add docs/protocol-discovery/gatt-census.md
git commit -m "docs: record ContryMod GATT census"
```

### Task 4: Validate the recovered protocol at the AC

**Files:**
- Create: `docs/protocol-discovery/command-validation.md`
- Local-only: `artifacts/ble-captures/command-validation-<UTC timestamp>.txt`

- [ ] **Step 1: Record the physical baseline before issuing any writes**

Create `docs/protocol-discovery/command-validation.md` only after the AC’s initial power, target temperature, mode, and recirculation state are physically observed. Record that complete baseline and the initial decoded state frame. Then add a result table with columns for sequence, action, exact outbound frame, acknowledgement/state frame, physical result after 10 seconds, and pass/fail. Its sequence must be: baseline read; power on; temperature +1 °; temperature −1 °; each app-exposed HVAC mode; recirculation on; recirculation off; and baseline restoration.

- [ ] **Step 2: Validate connection and state read before writing**

Connect to the exact characteristic identified in Tasks 2–3 and execute the recovered initial state/read handshake. A decoded frame must account for the physical baseline power state, target temperature, selected mode, and recirculation state. If any field disagrees, stop before the first write and update the static analysis/census evidence.

- [ ] **Step 3: Issue commands in the recorded order, one at a time**

For every sequence row, send only the recovered complete frame, wait 10 seconds, and record outbound bytes, any notification or acknowledgement bytes, and the physical result. Do not combine commands, retry a command automatically, or infer success solely from a transport write completing.

- [ ] **Step 4: Restore the initial AC state**

Use only commands that already passed physical validation to return the AC to the sequence-0 state. Record the restoration frame and result in row 7.

- [ ] **Step 5: Define pass/fail evidence**

Mark a row `pass` only when the outgoing frame, expected acknowledgement/state frame, and a physical change all agree. Mark it `fail` if any one is missing or disagrees; include the exact observed bytes and do not reuse that command in the integration plan.

- [ ] **Step 6: Commit redacted validation results**

```bash
git add docs/protocol-discovery/command-validation.md
git commit -m "docs: validate ContryMod BLE control frames"
```

The committed document contains frame formats and anonymized samples only. Raw transcripts remain under ignored `artifacts/ble-captures/`.

### Task 5: Publish the protocol contract and hand off to integration implementation

**Files:**
- Create: `docs/protocol-discovery/protocol-contract.md`

- [ ] **Step 1: Write the protocol contract from passing evidence only**

Create `docs/protocol-discovery/protocol-contract.md` with sections for device fingerprint, connection sequence, characteristics, frame format, commands, state frame, and failure semantics. Every table cell must contain an observed value with its JADX source-class path and one passing validation-sequence number. Do not leave table cells blank and do not describe unvalidated commands as supported.

- [ ] **Step 2: Check the contract against required controls**

Run:

```bash
rg -n 'Power|Temperature|HVAC mode|Recirculation' docs/protocol-discovery/protocol-contract.md
```

Expected: each required control appears once in the Commands table with a passing validation sequence. If any does not, stop the handoff and continue discovery instead of planning an unsupported integration feature.

- [ ] **Step 3: Commit the contract**

```bash
git add docs/protocol-discovery/protocol-contract.md
git commit -m "docs: define ContryMod BLE protocol contract"
```

- [ ] **Step 4: Create the second implementation plan only after contract approval**

The next plan uses `docs/protocol-discovery/protocol-contract.md` as its protocol authority and creates `custom_components/contrymod_ac/`, config flow, coordinator, climate platform, recirculation switch, diagnostics, translations, and fixture-driven tests. It must include the exact UUIDs, command construction, decoder, and test fixtures captured above.
