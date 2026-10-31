# Sensors integration plan (2026-10-31)

Sources: `out/ref/ubuntu-surface-pro-11/SENSORS.md`, `systemd/`, `sensors/sns_reg.conf`, `install.sh`; `sources/windows/DriverStore/surfacepro_snscfgcrd8380.inf_arm64_f5d7e051fecc22c3`, `surfacepro_ext_adsp8380...`; `sources/windows/live-inventory/sensors/` (registry mapping lists, WinRT sensor list); Fedora 44 repoquery in the aarch64 container; web search (libssc, iio-sensor-proxy MR 381). No REA session was opened: the format questions were answered from the INF/registry/config data (protocol section 9, order 1-3). Grades: Verified, Inference, Unknown.

## 1. What Windows does (Verified from data)

- Two sensor-platform devices `MSHW048A` (display side) and `MSHW048B` (second instance); `REGISTERED_SENSORS` of 048A: `rotv, gyro_cal, mag_cal, gravity, accel, gyro, mag, sar, proximity, game_rv, color, hinge_angle, pressure, transport_ppe` (`registry-MSHW048A.txt`). WinRT sees accelerometer, gyrometer, compass, magnetometer, light, inclinometer, orientation, simple orientation; no barometer, proximity, hinge angle (`winrt-sensors.txt`).
- `qcSensors.dll` (UMDF) serves the ADSP over FastRPC through a registry path map (`Mappings\FASTRPC`, 79 entries): `\vendor\etc\sensors\config\*` -> files of `surfacepro_snscfgcrd8380` (65 JSON names in `json.lst`, calibration `.bin`, camera `.pb`), and `\sys\devices\soc0\{hw_platform,soc_id,revision,platform_subtype,platform_subtype_id,platform_version}` -> static package files with values `CRD`, `615`, `3.1`, `Unknown`, `65536`, `0`.
- `sns_reg_config` (package file) tells the ADSP registry code: inputs `json.lst`, config dir `/vendor/etc/sensors/config`, output `/persist/sensors/registry/registry`. The map list has no `\persist` entry; the output location on Windows is therefore handled outside the registry map. Not decoded.
- The Windows `DriverData\Qualcomm\fastRPC\persist\sensors\registry\registry` tree (the 321 pre-parsed files the reference copies) is **not** in `sources/windows` and not on this device's C: (`System32\DriverData` does not exist). So we cannot copy it; Verified by listing.

## 2. Reference stack (their report; Inference)

`hexagonrpcd` (custom build of `linux-msm/hexagonrpc`: method 24 stub, write support, O_RDWR fallback) serves `/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors` to the ADSP `sensorspd` through `/dev/fastrpc-adsp`, early in `sysinit.target`, with `soc_id 555`, `CRD`, `2.1` written to `/run/sensors-platform`. The SNS framework reads the pre-parsed registry, then keeps running even when the daemon crashes on `fstempfile` writes. 13 SSC types give data: accel and gyro (ST LSM6DSV, SPI), mag (AKM AK0991x), light and colour (AMS TCS3430), SAR, gravity, rotation vectors, compass, fast and relative motion. Not available: proximity (TMD2755, no SUID), pressure, hinge angle, step and tilt. Reads through `libssc` (`ssccli`, their `sp11-sensor-read`). Tablet mode is SSAM, not SSC. Do not reset the ADSP remoteproc (SoC crash).

Consistency check with Windows: the sensor chips named by the reference (`lsm6dsv`, `ak991x`, `tcs3430`, `lps22df`, `tmd2755`) are exactly the JSON files in the Windows package, and the Windows `REGISTERED_SENSORS` list contains `pressure` and `proximity` that they report as unavailable. Verified (file names). Chip-to-bus facts stay Inference (JSON content not read for this plan).

## 3. Is the registry necessary? Unknown, decision

Reference claim: the ADSP needs `oemconfig.so` to parse JSON into the registry, which does not exist off Android, hence the copy from Windows. Counter-evidence: on Windows the same JSON inputs and `sns_reg_config` are served and a registry results without any Hexagon `oemconfig` file in the ADSP package (`surfacepro_ext_adsp8380/ADSP/` has only `libsns_*_skel.so` and codecs). Inference: the ADSP firmware (or `qcSensors.dll`) parses on first start. Unknown which. Plan, both paths supported by the script:

1. **P1 (default)**: stage config, `sns_reg.conf` and platform files from `sources/windows` and leave `registry/` empty; hexagonrpcd with write support lets the ADSP create it on first boot. Test: files appear under `.../sensors/registry/`.
2. **P2 (fallback)**: `--registry-from DIR` for a pre-parsed Windows registry. The operator would have to capture it from a live Windows `DriverData` (not present on the dump); if P1 fails the sources worker adds that capture to the Windows dump request.

Platform values: use the Windows package values (`CRD`, `615`, `3.1`) in P1. The JSON filters accept `555`, `615`, `616`, `635` (reference text), so the reference's `555`/`2.1` is a second candidate if P1 yields no sensors.

## 4. Fedora packages (Verified by `dnf repoquery` in `registry.fedoraproject.org/fedora:44`, aarch64)

| Piece | Fedora 44 | Note |
|:--|:--|:--|
| `fastrpc`, `fastrpc-services`, `hexagon-dsp-binaries*` | present | `fastrpc-services` starts `adsprpcd`, `adsprpcd_audiopd` from udev on `/dev/fastrpc-adsp`: conflicts with hexagonrpcd for the ADSP listener; mask both on this image (Inference) |
| `hexagonrpcd` / `libhexagonrpc` | **absent** (no match for `*hexagonrpc*`) | upstream `github.com/linux-msm/hexagonrpc` v0.5.0, GPL-3.0. v0.4.0..v0.5.0 commits are interp4 refactor, systemd units, endian fixes: none mentions method 24 or write support, so the reference patch is still needed (Unknown whether upstream has it elsewhere). Build locally (spec in `image/`), mark source `linux-msm/hexagonrpc` pinned by hash |
| `libssc`, `ssccli` | **absent** (no `*ssc*`) | upstream is on Codeberg (`zff.dev/agx/libssc` page); licence unverified |
| `iio-sensor-proxy` | 3.8-2.fc44 present, **without SSC support** (no `libssc` string in the binary; requires only glib, gudev, polkit) | libssc support is a separate merge request (`gitlab.freedesktop.org/hadess/iio-sensor-proxy/-/merge_requests/381`, open in the results I found; status may have changed). postmarketOS carries it |
| `qrtr`, `qrtr-libs`, `libqrtr-glib`, `libqmi` | present | kernel provides `qrtr-ns`; libssc needs `AF_QIPCRTR` (a sandboxed service must allow it) |

## 5. Design

- Public ISO: no sensor stack. (Config JSON and calibration blobs are Windows material.)
- Private image: build RPMs locally (not in Fedora): `hexagonrpcd` (+ the Ubuntu-style write/method-24 patch, to be written or re-derived: not published), `libssc`, and an `iio-sensor-proxy` rebuilt with MR 381. Stage the tree with `userspace/sp11-sensors-stage.sh`, install at `/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors`, units `userspace/sensors-platform-info.service` and `userspace/hexagonrpcd-sensors.service`, mask `adsprpcd*.service`.
- Order: ADSP `running` and `/dev/fastrpc-adsp` present (works in M13) -> platform info -> hexagonrpcd. The ADSP does not depend on the CDSP, so sensors can proceed while the CDSP is stuck. Hence sensors are testable now, if the image carries the pieces.
- Rotation: `iio-sensor-proxy` (SSC build) publishes `AccelerometerOrientation` to the compositor (GNOME) and light for auto brightness. Tablet mode: `surface_aggregator_tabletsw` (KIP switch, `hardware/ec-sam`), independent of SSC. Interaction between display orientation and the Type Cover posture is a compositor policy; no kernel part.
- ALS auto-brightness acceptance needs the display owner's backlight control (a request).

## 6. Open questions

| # | Question | Grade | Answered by |
|:--|:--|:--|:--|
| S1 | Does the ADSP generate the registry itself from the Windows JSONs (P1)? | Unknown | one boot of the private image |
| S2 | Is a hexagonrpcd with method 24 / write support needed, and is that patch published? | Unknown | read the reference's binary source or `journalctl -u hexagonrpcd` on the device |
| S3 | iio-sensor-proxy MR 381 merged and in which release? | Unknown | upstream check at packaging time |
| S4 | Does the display-side sensor (048A) or keyboard-side (048B) provide the screen accelerometer? JSON names `8380_crd_lsm6dsv_display.json` and `..._keyboard.json` | Inference (names) | libssc sensor list on device; keyboard-side data absent when the cover is detached |
| S5 | Which `soc_id` does the ADSP expect (`615` Windows or `555` reference)? | Unknown | P1 test, then fallback |

## 7. Asks

- **image**: private mode only: build `hexagonrpcd`, `libssc`, SSC-enabled `iio-sensor-proxy` RPMs locally, install the staged tree and the two units from `hardware/sensors/userspace/`, mask `adsprpcd.service` and `adsprpcd_audiopd.service`, add group/permissions for `/dev/fastrpc-adsp` (hexagonrpcd runs as root or `fastrpc`). Run `sp11-sensors-stage.sh --windows sources/windows --out out/sensors-private/stage` before the stage step; the output never enters git.
- **sources**: if P1 fails, capture the Windows `DriverData\Qualcomm\fastRPC\persist\sensors\registry\registry` tree (321 files in the reference) with a read-only script, private (S5); pin hexagonrpc v0.5.0 and libssc source as inputs.
- **kernel**: confirm `CONFIG_QCOM_FASTRPC`, `CONFIG_QRTR` (already `m`), `CONFIG_SURFACE_AGGREGATOR_TABLET_SWITCH=m` (`hardware/ec-sam` R2 already asks).
- **ec-sam**: tablet-mode acceptance stays theirs.
- **display-lcd / audio owners**: none.
