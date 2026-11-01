# sensors

## 1. Summary

Motion, orientation and light sensors attached to the ADSP sensor core (SSC). Windows reaches them through `MSHW048A`/`MSHW048B`; Linux has no kernel driver and reaches the SSC from userspace over FastRPC/QMI. Status: `testing` (M15.1 reached the daemon, but device function is not demonstrated; logs exposed registry path and seed ownership mismatches that need an image composition fix).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_MSHW&DEV_048A&SUBSYS_MSHW0487` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_048B&SUBSYS_MSHW0487` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `Simple Device Orientation Sensor` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcsensors` | TBD |
| `surfacepro_snscfgcrd8380` | TBD |
| `sensorshidclassdriver` | TBD |
| `sensorsalsdriver` | TBD |
| `sensorsservicedriver` | TBD |

## 4. Linux 7.3

- Driver: `misc/fastrpc`
- Driver: `userspace: hexagonrpcd, libssc, iio-sensor-proxy`
- Nothing in the DT.
- Local RPMs in `out/rpms-local/` (hexagonrpcd 0.5.0 + write patch, libssc 0.4.4, iio-sensor-proxy 3.9 with SSC, `sp11-sensors` glue): [build evidence](evidence/2026-10-31-sensors-build.md).
- Native coverage: **none** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no kernel driver: SSC is reached over FastRPC/QMI from userspace | built: `hexagonrpcd` (write patch), `libssc`, `iio-sensor-proxy` 3.9 + `sp11-sensors` (`userspace/rpm/`); needs a device boot |
| physical sensor chips | read from the JSON: LSM6DSV (accel/gyro, display and keyboard), AK0991x (magnetometer), TCS3430 (light, colour), TMD2755 (proximity, config file truncated), LPS22DF (pressure) (evidence 2026-10-31-sensors-build.md section 4.3) |
| sensor registry/config files | config (70 files), identity (6) and 293 generated registry files staged privately in `out/firmware-private/sensors/`; M15.1 installed seeds one level above `sns_reg.conf`'s configured output; files are also 1000:1000 mode 0640 while the daemon user is 983:984. Image composition must place new seeds at the nested output and assign service ownership without changing existing state. ADSP state-file generation and 20 to 25 unexplained reference files remain Unknown ([boot evidence](evidence/2026-11-01-m15.1-logs.md)) |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which physical chips are present? | TBD | Sensor registry/config files in `surfacepro_snscfgcrd8380` and the ADSP package |
| Q2 | Is the Linux userspace stack (`hexagonrpcd`, `libssc`, `iio-sensor-proxy`) packaged for Fedora 44? | Verified: no; `hexagonrpcd` and `libssc` absent, `iio-sensor-proxy` 3.8 has no SSC; local RPMs built from pinned upstream (iio-sensor-proxy 3.9 is the first release with SSC) | n/a |
| Q3 | Which registry files must be installed and where? | Verified path: `sns_reg.conf` output is `/persist/sensors/registry/registry`; Linux mapping makes this `<root>/sensors/registry/registry` (symlinked to `/var/lib/hexagonrpcd/registry/registry`). M15.1 seeds were in the parent, generated names differ from ADSP requests, and files are not readable by the daemon account; image composition change is proposed, with ADSP acceptance still unverified. | next private ISO boot; read-only test plan |

## 7. Acceptance

1. Screen rotates with the device
2. Ambient light is readable for diagnostics only; automatic brightness is disabled by operator decision (dconf `ambient-enabled=false` and locked). Brightness must NOT change when the ALS is covered/uncovered.

## 8. Requests

- **sources** (`sources/sources.toml`, `sources/README.md`): pin three inputs, tables in [build evidence](evidence/2026-10-31-sensors-build.md) section 9 and in `userspace/rpm/pins.toml`: `[hexagonrpcd]` linux-msm/hexagonrpc v0.5.0 (commit 435ed1cd..., SHA-256 2173985932ab...), `[libssc]` DylanVanAssche/libssc v0.4.4 (commit 0cf77b93..., SHA-256 716d6bd6...), `[iio-sensor-proxy]` 3.9 (commit 0085ddf8..., SHA-256 19a4ae99...). The build script already prefers `sources/sources.toml` and falls back to `pins.toml` with a warning. Also (only if both registry routes fail): a read-only capture of the Windows `DriverData\Qualcomm\fastRPC\persist\sensors\registry\registry` tree (private, S5).
- **image** (all file paths under `hardware/sensors/userspace/`; details in build evidence sections 3 and 6):
  - packages from `out/rpms-local/`: `hexagonrpcd`, `libssc`, `libssc-tools`, `iio-sensor-proxy` 3.9, `sp11-sensors` (public-safe, no Windows material; `sp11-sensors` pulls the others). Build or refresh with `hardware/sensors/userspace/build-sensors-rpms.sh` (a local repo, like the iptsd RPM).
  - private mode only: `sp11-sensors-stage.sh --windows sources/windows --out out/firmware-private/sensors` (already staged), then `sp11-sensors-install-private.sh --stage out/firmware-private/sensors --root <rootfs>`; M16 should place newly staged seeds at `/var/lib/hexagonrpcd/registry/registry` and set owner/group from the target rootfs `hexagonrpcd:fastrpc`, mode 0640, during composition. Do not recursively chown existing persistent registry data. Seed names remain unverified against the ADSP; run the read-only test plan and keep the ISO private.
  - units are enabled by the package preset; **do not mask `adsprpcd*.service`** (supersedes the integration plan); no 0666 udev rule.
  - L0 assertions: build evidence section 6. Collector drop-in is `/etc/sp11-log-collector.d/sensors.sh` (shipped in `sp11-sensors`; same file as `userspace/collector/sensors.sh`).
- **kernel**: confirm `CONFIG_QCOM_FASTRPC`, `CONFIG_QRTR` and `CONFIG_QRTR_SMD` (or the transport that carries the ADSP SSC service), `CONFIG_SURFACE_AGGREGATOR_TABLET_SWITCH=m` in the final config; the daemon needs the FastRPC sensors-PD attach ioctl (present in 7.3, not re-read here).
- **power-thermal**: the suspend hook with the corrected `ConditionFirmware=device-tree-compatible(qcom,x1e80100)` is `hexagonrpcd-sensors-sleep.service` (there are no Debian hook units on Fedora to override); ladder results with it enabled are welcome.
- **ec-sam**: tablet-mode acceptance stays theirs; `sp11-sensors-test` section 6 reads the switch state read-only.
- **display-lcd**: no action needed for this component: automatic brightness is removed by operator decision and the image locks `ambient-enabled=false` (commit `2ee4dbf`); the earlier request for backlight control for ALS auto-brightness is withdrawn. Do not wire the ALS to the backlight.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-31: Windows sensor model read from INF and live registry mappings (config files and `soc0` identity are static package files; registry tree absent from the dump); Fedora package status checked; staging script and units written; sensors do not depend on the CDSP and can be tested as soon as the private image carries the pieces.
- 2026-10-31: sensors build: upstream pins (hexagonrpc v0.5.0, libssc v0.4.4, iio-sensor-proxy 3.9 = first release with SSC); write-capable hexagonrpcd patch (method 24 is fremove); `sscregistrygen` found in upstream and used to generate 293 registry files from `sources/windows`; five RPMs built, linted and installed in a scratch root; units, rules, stage/install scripts, read-only test and collector written; evidence `2026-10-31-sensors-build.md`. Nothing run on the device.
- 2026-11-01: M15.1 journal and collector evidence show repeated ENOENT at configured registry paths: seeds were installed in the parent, generator names differ from ADSP requests, and staged file ownership does not match the service user. Requested an image composition change to place new seeds at the configured nested path with service ownership; existing state must remain untouched. Daemon reaches ADSP/QRTR but sensor events and brightness response remain unverified; evidence `2026-11-01-m15.1-logs.md`.
- 2026-11-01: automatic brightness removed by operator decision. The ALS itself remains present (Windows WinRT `LightSensor: PRESENT` on MSHW048A, TCS3430 config, `sensorsalsdriver` package) and is diagnostic only; acceptance and test plan now require no brightness change on cover/uncover. The image lock in commit `2ee4dbf` is referenced, not duplicated. Evidence `2026-11-01-auto-brightness-removed.md`.
