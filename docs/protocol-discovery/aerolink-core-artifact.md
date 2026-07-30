# AeroLink Core Android artifact and static BLE analysis

## Artifact record

| Field | Observed value |
| --- | --- |
| Official store URL | https://play.google.com/store/apps/details?id=com.kingcontech.btac |
| Package identifier | `com.kingcontech.btac` |
| Artifact source URL | https://apkcombo.com/d?u=aHR0cHM6Ly96dHAtcGlnLmFwa2NvbWJvLmNvbS94YXBrL2NvbS5raW5nY29udGVjaC5idGFjLzQzNGEyZDI2NzJhNDQ4Y2M5ZGMyMmVkNGRiNDlkNWJhL2Rvd25sb2FkP25hbWU9Y29tLmtpbmdjb250ZWNoLmJ0YWNfMS4wLjAueGFwayZfX2NhY2hlPXRydWU= |
| Download UTC | `2026-07-30T19:04:21Z` |
| Download container | APKCombo XAPK; inspected APK is its `com.kingcontech.btac.apk` member |
| APK SHA-256 | `9a5d8ed317fe840ec7bda160a12b645420c6a0961e45096bcd95c2ced197f674` |
| AndroidManifest.xml SHA-256 | `695ede563b173ecd96f4ce03f3ab248f55997bb6ad31e05459f696595b969e22` |
| Version name / code | `1.0.0` / `1005` |
| Signing certificate SHA-256 | `f203191199acc1d19f657139888c838e2252ddb1530b073225be3b0b1f7b23c2` |
| Source Stamp signer certificate SHA-256 | `3257d599a49d2c961a471ca9843f59d341a405884583fc087df4237b733bbd6d` |

APKCombo's page identifies AeroLink Core as `com.kingcontech.btac`, version `1.0.0` (code `1005`). `apksigner` verified APK Signature Scheme v3 and Source Stamp. The APK signer DN is `CN=Android, OU=Android, O=Google Inc., L=Mountain View, ST=California, C=US`.

## Analysis provenance

The APK was decompiled without modification using JADX `1.5.6`:

```text
jadx --deobf --show-bad-code -d artifacts/aerolink-core/jadx artifacts/aerolink-core/AeroLink-Core.apk
```

The application-specific implementation is the UniApp bundle at `artifacts/aerolink-core/jadx/resources/assets/apps/__UNI__5C5F035/www/app-service.js`. It is minified onto JADX line 21, but preserves original-source markers such as `common/blueTooth.js:712` and `pages/ctrlPanel_v2/index.vue:227`; named functions and those markers below are the source evidence.

## Static BLE findings

| Topic | Observed finding | JADX evidence |
| --- | --- | --- |
| Scan filter | QR pairing passes its scanned name to `dn.startBluetoothDevicesDiscoveryNext`, which calls `uni.startBluetoothDevicesDiscovery({allowDuplicatesKey:true})` with no service UUID, manufacturer-data, or RSSI filter. It accepts only `device.name == name` or `device.localName == name`, with a 50-result counter. Manual search has no native scan filter and retains names containing `KT`. | `app-service.js`, device-list `openScan`, `activeBlue`, `scanDevice`; `dn.startBluetoothDevicesDiscoveryNext`, `common/blueTooth.js:909-927`; `pages/deviceList/index.vue:142,232`. |
| Connection / discovery | `dn.firstConnectNext` calls `uni.createBLEConnection`, then `uni.getBLEDeviceServices` and `uni.getBLEDeviceCharacteristics` against the hard-coded service; it logs results but does not select UUIDs dynamically. | `app-service.js`, `dn.firstConnectNext`, `common/blueTooth.js:197,214,221`. |
| Service UUID | `0000FFE0-0000-1000-8000-00805F9B34FB` | `app-service.js`, `dn.serviceId`. |
| Notify characteristic UUID | `0000FFE1-0000-1000-8000-00805F9B34FB`; `dn.openNotify` calls `uni.notifyBLECharacteristicValueChange({state:true,...})`, then sends values to `un`. | `app-service.js`, `dn.readcid`, `dn.openNotify`, `common/blueTooth.js:430`. |
| Write characteristic UUID | `0000FFE2-0000-1000-8000-00805F9B34FB`; recovered command paths call `uni.writeBLECharacteristicValue` on `dn.writecid`. | `app-service.js`, `dn.writecid`, `dn.disposeMsg` at `common/blueTooth.js:712-718`, and `dn.bleSendData` at `common/blueTooth.js:813`. |
| Read characteristic | No application-level `uni.readBLECharacteristicValue` invocation was found in the inspected application bundle; `readcid` is its notification target, not evidence of a GATT read. | `rg -o -i 'readBLECharacteristicValue' app-service.js` returned count `0`; `dn.openNotify`. |
| Command framing / checksum | `dn.bleSendData` and `dn.disposeMsg` allocate `Uint8Array(9)`: `[5A,5A,5+L,K,C,V,(B9+L+C+V+K) mod 256,0D,0A]`. `L` is the caller's first argument, `K=kindCode`, `C=command`, and `V=value`. The controls below use `L=1`, so byte 2 is `06`. | `app-service.js`, `dn.bleSendData` (`common/blueTooth.js:813`) and `dn.disposeMsg` (`common/blueTooth.js:712-718`). |
| Incoming notification / checksum | `un` buffers values, finds `5A 5A` and `0D 0A`, and passes a complete frame to `Gt`. `Gt` rejects <19-byte frames, bad header/trailer, and a checksum other than `(sum bytes 0 through length-4) mod 256`; it parses power, primary mode, fan speed, screen flag, turbo/auto/eco/sleep/swing/negative-ion/light/wind-side flags, temperatures, currents, voltage, under-voltage, fault, timer, temperature unit, and target temperature. | `app-service.js`, `un` (`common/blueTooth.js:402,409`) and `Gt` (`common/device.ts:180,185,190,200`). |
| Activation / authentication | Standard QR and manual-add paths call `dn.firstConnectItem(deviceId,1,1,...)`, which sends `[5A 5A 06 01 42 01 FE 0D 0A]` before enabling notifications. Reconnects source `K` from persisted `deviceCtrlList[e].key`; newly created records set `key:1`. No AES, encryption, decryption, cipher, crypto, CRC, checksum function, challenge, nonce, password, pair, or bond token was present in the inspected application bundle. | `app-service.js`, device-list `connect_device`/`activeBlue`/`activeDevice`; `dn.firstConnectNext` (`common/blueTooth.js:197-304`); corresponding token scan returned count `0`. |

## UI controls traced to wire frames

The current v2 UI follows `Xt` (`pages/ctrlPanel_v2/index`) dispatch object `_` → `T(1,command,value)` → `dn.sendMsg` → `dn.bleSendData`. The legacy `pages/ctrlPanel/index` uses the same builder and control codes. `K=01` is the observed app-created connection value.

| App control and UI mapping | Command/value | Exact frame for `K=01` | Source evidence |
| --- | --- | --- |
| Power on | `C=01`, `V=02` | `5A 5A 06 01 01 02 BE 0D 0A` | `Xt._.Power`; `xt.OFF=0`, `xt.ON=1`; `Dt=1`; `dn.bleSendData`. |
| Power off | `C=01`, `V=01` | `5A 5A 06 01 01 01 BD 0D 0A` | Same handler sends `01` when current `c.power` is `ON`. |
| Temperature, Celsius | UI permits every integer `16..30` when `temperature_unit=0`; it sends the displayed integer as `V`, `C=03`. For `T` in `16..30`: `5A 5A 06 01 03 TT ((BE+TT) mod 256) 0D 0A`. | `yt` `TemperatureCtrl` (`s=16`, `c=30`, function `r` and setter `w`); `Xt._.Temperature`; `Ft=3`. |
| Temperature, Fahrenheit | UI permits every integer `61..86` when `temperature_unit=1`, sent directly as `V`, `C=03`; for `T` in `61..86` it uses `5A 5A 06 01 03 TT ((BE+TT) mod 256) 0D 0A`. Unit selection sends `C=20,V=01` for Celsius or `C=20,V=02` for Fahrenheit. | `yt` `TemperatureCtrl`; `Xt._.Temperature`; `Xt._.SettingTemperatureUnit`; `zt=32`. |
| Cooling | `C=02`, `V=01` | `5A 5A 06 01 02 01 BE 0D 0A` | `qt.ModeCtrl.g`: `bt.COOL=1` → `Bt.COOL=1`; `Xt._.WorkMode`; `It=2`. |
| Dehumidification (label `Dehumid`) | `C=02`, `V=07` | `5A 5A 06 01 02 07 C4 0D 0A` | `qt.ModeCtrl.g`: `bt.DRY=2` → `Bt.DRY=7`; `Xt._.WorkMode`. |
| Fan | `C=02`, `V=02` | `5A 5A 06 01 02 02 BF 0D 0A` | `qt.ModeCtrl.g`: `bt.FAN=3` → `Bt.FAN=2`; `Xt._.WorkMode`. |
| Heating | `C=02`, `V=08` | `5A 5A 06 01 02 08 C5 0D 0A` | `qt.ModeCtrl.g`: `bt.HEAT=4` → `Bt.HEAT=8`; `Xt._.WorkMode`. |
| Turbo | `C=02`, `V=06` | `5A 5A 06 01 02 06 C3 0D 0A` | `qt.ModeCtrl.v`: `bt.TURBO=6` → `Bt.TURBO=6`; only powered on and not Fan/Dry; `Xt._.FuncChange`. |
| Auto | `C=02`, `V=09` | `5A 5A 06 01 02 09 C6 0D 0A` | `qt.ModeCtrl.v`: `bt.AUTO=8` → `Bt.AUTO=9`; same condition; `Xt._.FuncChange`. |
| Eco | `C=02`, `V=04` | `5A 5A 06 01 02 04 C1 0D 0A` | `qt.ModeCtrl.v`: `bt.ECO=7` → `Bt.ECO=4`; same condition; `Xt._.FuncChange`. |
| Sleep | `C=02`, `V=05` | `5A 5A 06 01 02 05 C2 0D 0A` | `qt.ModeCtrl.v`: `bt.SLEEP=5` → `Bt.SLEEP=5`; same condition; `Xt._.FuncChange`. |
| Inner wind-side action | `C=44`, `V=00` | `5A 5A 06 01 44 00 FF 0D 0A` | `qt.ModeCtrl.y`: `kt.WINDSIDE_INNER` → `Ot.INNER=0`; `Xt._.WindSide`; `Ht=68`. |
| Outer wind-side action | `C=44`, `V=01` | `5A 5A 06 01 44 01 00 0D 0A` | `qt.ModeCtrl.y`: `kt.WINDSIDE_OUTER` → `Ot.OUTER=1`; `Xt._.WindSide`; `Ht=68`. |
| Wind speed | The v2 `WindCtrl` clamps each UI change to `W=1..6`; `Xt._.WindSpeed` sends `C=04,V=W`. For every such `W`: `5A 5A 06 01 04 WW ((BF+WW) mod 256) 0D 0A`. | `app-service.js`, `St` `WindCtrl` function `d`; `Xt._.WindSpeed`; `Pt=4`; `Xt` dispatch `T` at `pages/ctrlPanel_v2/index.vue:227`. |
| Light | While powered on, `qt.ModeCtrl.y` cycles the UI value `0 → 1 → 2 → 0`; `Xt._.Light` sends decimal `C=28` (`1C` on the wire), `V=L`. Frames are `L=00`: `5A 5A 06 01 1C 00 D7 0D 0A`; `L=01`: `5A 5A 06 01 1C 01 D8 0D 0A`; `L=02`: `5A 5A 06 01 1C 02 D9 0D 0A`. | `app-service.js`, `qt.ModeCtrl.y`; `Xt._.Light`; `At=28`; `Xt` dispatch `T` at `pages/ctrlPanel_v2/index.vue:227`. |
| Screen-display toggle | `qt.ModeCtrl.y` emits `!screenDisplay`; `Xt._.ScreenDisplay` maps Boolean `true` to decimal `C=10` (`0A` on the wire), `V=02`, and Boolean `false` to `C=10,V=01`. Frames are `true`: `5A 5A 06 01 0A 02 C7 0D 0A`; `false`: `5A 5A 06 01 0A 01 C6 0D 0A`. The inspected source does not state which logical value means the physical screen is on. | `app-service.js`, `qt.ModeCtrl.y`, `Xt._.ScreenDisplay`; `Ut=10`; `Xt` dispatch `T` at `pages/ctrlPanel_v2/index.vue:227`. |
| Swing toggle | `qt.ModeCtrl.y` sends `0` when current `swing==1`, otherwise `1`; `Xt._.Swing` sends decimal `C=69` (`45` on the wire), `V=S`. Frames are `S=00`: `5A 5A 06 01 45 00 00 0D 0A`; `S=01`: `5A 5A 06 01 45 01 01 0D 0A`. | `app-service.js`, `qt.ModeCtrl.y`, `Xt._.Swing`; `Mt=69`; `Xt` dispatch `T` at `pages/ctrlPanel_v2/index.vue:227`. |
| Under-voltage selector | `Nt` `SettingCtrl` renders the visible `under_voltage` selector and emits its selected value `U`. It offers `U=9..12` when device voltage is `8..17`, `19..24` for `18..35`, and `37..42` for `36..48`; otherwise the selector list is empty. `Xt._.SettingUnderVoltage` calls `T(1,Rt,10×U)`, with decimal `C=5`. Because the shared builder stores this raw value in `Uint8Array`, wire byte `VV=(10×U) mod 256`; its exact frame is `5A 5A 06 01 05 VV ((C0+VV) mod 256) 0D 0A`. | `app-service.js`, `Nt` `SettingCtrl`, `Tt` UVP value sets, and its `underVoltageChange` event; `Xt._.SettingUnderVoltage` calls `T(1,Rt,10*e)`; `Rt=5`; `Xt` dispatch `T` at `pages/ctrlPanel_v2/index.vue:227`. |
| Timer enable / disable | `qt.ModeCtrl` emits enabled only when the selected hour or minute-index is nonzero. `Xt._.SettingTimer` sends decimal `C=22` (`16` on the wire), `V=02` to enable: `5A 5A 06 01 16 02 D3 0D 0A`; disable sends `C=22,V=03`: `5A 5A 06 01 16 03 D4 0D 0A`. | `app-service.js`, `qt.ModeCtrl` function `h`; `Xt._.SettingTimer`; `$t=22`; embedded `pages/ctrlPanel_v2/index.vue:340-341`. |
| Timer value | After enabling, `Xt._.SettingTimer` sends decimal `C=24` (`18` on the wire), `V=P`, where `P=((H & 0F)<<4) | (M & 0F)`. `H` is UI hour `0..11`; `M` is the UI minute-picker index `0..12` (display labels are `0,5,...,60`; the code packs the index, not the displayed minute). Frame: `5A 5A 06 01 18 PP ((D3+PP) mod 256) 0D 0A`. | `app-service.js`, `qt.ModeCtrl` functions `h`/`d`; `Xt._.SettingTimer`; `Wt=24`; `pages/ctrlPanel_v2/index.vue:340-341`. |

## Limitations

- The source is APKCombo, not a signed-in Google Play delivery. The valid v3 signer and Google Source Stamp support Google distribution, but cannot prove this is the exact current APK Google Play would deliver for a particular account, device configuration, country, or time. This record does not claim official Google Play artifact provenance.
- JADX completed with 95 decompilation errors in framework/library code. The relevant app logic was present in its readable, minified `app-service.js` asset.
- Static analysis identifies intended UUIDs and calls, not a controller's live GATT table, handles, properties, or responses. No BLE command, pairing, or controller connection was performed.
- Requested recirculation on/off semantics are unvalidated: the app frames named **inner** and **outer** wind-side actions, but never calls either recirculation or maps either to recirculation on/off. The exact frames are recorded above; assigning that semantic would be a guess.
- The listed temperature range is the full app UI range and its direct-byte encoding, not proof of controller acceptance. All command mappings remain statically recovered and unvalidated pending the GATT census and physical validation tasks.
- Wind speed, light, screen-display, swing, under-voltage, and timer entries are additional app-visible controls recorded for static completeness only; this document makes no claim that any is a supported version-1 integration control.
