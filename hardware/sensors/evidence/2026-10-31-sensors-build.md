# Sensors build and integration (2026-10-31)

Worker: sensors. No REA session was opened (protocol section 9, order 1-3: upstream sources, INF and JSON data). Grades: Verified (read from data, built, or run here), Inference, Unknown (only the device can answer). Companion to `2026-10-31-sensors-integration.md` and `2026-10-31-rea-registry.md`; corrections to those two files are in section 8.

## 1. Upstream sources, pinned (Verified by API and by hashing the archives)

| Piece | Upstream | Pin | Archive SHA-256 |
|:--|:--|:--|:--|
| hexagonrpcd | `github.com/linux-msm/hexagonrpc` (project name `hexagonrpc`, daemon `hexagonrpcd`), GPL-3.0-or-later | tag `v0.5.0`, commit `435ed1cd68e20f8a9fe4871233ed1f8ce7ccf9e8` (GitHub tags API) | `2173985932ab68d8ac593f9954357123bdbbbe9ba5f1b17a098d9cbcec22c5d5` |
| libssc | `codeberg.org/DylanVanAssche/libssc` (the project iio-sensor-proxy depends on; the Ubuntu reference clones the fork `DakkesheshRC/libssc`, not used here), GPL-3.0-or-later | tag `v0.4.4` (2026-06-27), commit `0cf77b93b55752da34dca2dcecc06fca8665184b`, annotated tag object `b08bb050313a3c90d408e9a72e06ead7f3eed6b7` (Codeberg API) | `716d6bd6b34d2d753060c6b54c9a87e34fae75b724c763bf9ef487efa3621587` |
| iio-sensor-proxy | `gitlab.freedesktop.org/hadess/iio-sensor-proxy`, GPL-3.0-or-later | tag `3.9` (2026-03-02), commit `0085ddf8ecb173a1c5fcf2344aa40e561125354f` (GitLab API) | `19a4ae99b1b8af603fc789841025f9747bf445418d69ec7389e75adb6c8186bf` (`.tar.bz2`, the URL Fedora's spec uses) |

- Question S3 of the integration plan is answered: MR 381 "libssc support" is **merged** (2026-02-08) and iio-sensor-proxy **3.9** is the first release with it (`meson.build` has `libssc_dep` with `-Dssc-support`, `src/drv-ssc-{accel,compass,light,proximity}.c`; NEWS 3.9: light and compass SSC drivers are on by default, accelerometer and proximity are experimental and need a udev rule). Fedora 44 ships 3.8-2 (no SSC); Fedora rawhide has 3.9 but builds it with `-Dssc-support=disabled` (rawhide spec read from `src.fedoraproject.org`) because libssc is not in Fedora.
- iio-sensor-proxy needs `libssc >= 0.2.1`; 0.4.4 satisfies it and was used in the build.
- GitLab does not promise stable archive bytes; the SHA-256 is the control and the build script refuses any mismatch.
- Fedora 44 aarch64 offers none of `hexagonrpcd`, `libssc`; `iio-sensor-proxy` is 3.8-2 (repoquery in `sp11-fedora-image:44`, recorded in `out/rpms-local/sensors-rpms.json`).
- `libssc` 0.4.4 has a compass class (`libssc-sensor-compass.h`) and `ssccli`; it has no classes for colour, SAR, gravity, rotation vector or motion. The reference's 13-sensor reader (`sp11-sensor-read`) uses libssc's generic report path for those; it is not part of this package set (Unknown: whether it needs the fork).

## 2. RPMs built and install-tested (Verified: built here, aarch64, `sp11-fedora-image:44`)

Output `out/rpms-local/` (not `out/rpms`), record `out/rpms-local/sensors-rpms.json` (RPM, source, spec, patch hashes, Fedora query, build package list). Build: `hardware/sensors/userspace/build-sensors-rpms.sh` (same container pattern as `scripts/image-build-iptsd.sh`; modes `build`, `check`, `install`). Specs and patches: `hardware/sensors/userspace/rpm/`.

| RPM | Content | SHA-256 |
|:--|:--|:--|
| `hexagonrpcd-0.5.0-1.sp11.fc44.aarch64` | `hexagonrpcd`, `sscregistrygen`, `libhexagonrpc.so.0.5`, `chrecd`, man page, sysusers file (user `hexagonrpcd`, member of `fastrpc`) | `fe9e952d...0831a37` |
| `libssc-0.4.4-1.sp11.fc44.aarch64`, `libssc-devel`, `libssc-tools` (`ssccli`) | library, headers and pkg-config, CLI | `01e8633b...cd381`, `d1142dcd...17679`, `6bbfaf22...183f8` |
| `iio-sensor-proxy-3.9-1.sp11.fc44.aarch64` | Fedora's layout (`monitor-sensor`, libexec, unit, `80-iio-sensor-proxy.rules`, D-Bus policy, polkit) built with `-Dssc-support=enabled` | `fafe4aa5...0c6c` |
| `sp11-sensors-1.0-1.fc44.noarch` | units, preset, udev rules, iio-sensor-proxy drop-in, opt-in test, collector drop-in; **no Windows or Qualcomm material** | `4a5594fc...5221b` |

Release `1.sp11` sorts above a future Fedora `1.fc44`, so a Fedora update cannot silently replace the patched build.

Checks run:

- `hexagonrpcd` `%check`: upstream `meson test` (iobuffer, hexagonfs) plus the new write test: 2/2 OK. `libssc` and `iio-sensor-proxy`: no tests run (the libssc mocking server needs AF_QIPCRTR loopback and python protobuf; umockdev is not in the container). Compiles clean apart from upstream `-Wunused-result` and one uninitialised-variable warning in iio-sensor-proxy.
- `rpmlint` (2.8.0): no packaging errors. Remaining output is spelling of technical words, missing man pages for `sscregistrygen`, `monitor-sensor`, `ssccli`, no `%check` for three specs, and one false positive (`explicit-lib-dependency libssc-tools`).
- `rpm -qpl` lists reviewed; `sp11-sensors` and the three others contain no `.mbn/.bin/.pb`, no `qcom/x1e80100` path and no DriverStore name (grep, "none").
- Install test (`build-sensors-rpms.sh install`: `dnf --installroot` in a scratch root with dependency resolution and scriptlets): all five install; user `hexagonrpcd` (uid 998) and group membership `fastrpc:...:hexagonrpcd` created from the sysusers file; preset enables `hexagonrpcd-sensors.service` and `hexagonrpcd-sensors-sleep.service`; `iio-sensor-proxy.service` is `static` (D-Bus activated, started by udev); D-Bus policy `net.hadess.SensorProxy.conf` and the polkit policy land; every binary resolves its libraries; `iio-sensor-proxy` contains 3 `ssc-*` driver strings. `systemd-analyze verify` of the two sp11 units prints nothing (the only message is a missing `dbus.socket` for `iio-sensor-proxy.service` in the minimal root). `udevadm verify` accepts `80-` and `81-`; for `61-` it reports "Unknown group fastrpc" because it resolves groups on the build host, not in `--root` (the group exists in the scratch root; Fedora's own `60-fastrpc.rules` uses the same group).

### 2.1 What the hexagonrpcd patch does (Verified: compiled and unit-tested; wire format Inference)

Upstream hexagonrpcd 0.5.0 is read-only: `mapped_openat` opens `O_RDONLY`, and `fopen_with_env` answers `w`/`a` with `AEE_EUNSUPPORTED` ("Tried to open ... for writing", `hexagonrpcd/apps_std.c`). It implements only `apps_std` methods 1, 2, 3, 4, 9, 19, 26, 27, 28, 31. The reference's "method 24" is **`fremove`**: the method order of `quic/fastrpc idl/apps_std.idl` (fopen 0, freopen 1, fflush 2, fclose 3, fread 4, fwrite 5 ... fsync 23, fremove 24, fileExists 22, opendir 26, stat 31) reproduces the five IDs hexagonrpcd already uses, so the numbering is Verified by that match.

`hexagonrpc-0001-apps_std-write-support.patch` adds: open flags from the stdio mode in `fopen_with_env`; `fopen` (0); `fwrite` (5); `fsync` (23); `fremove` (24) as a success stub (nothing is deleted); `hexagonfs_openat_flags` and a `write` file operation, effective only below a mapped directory (the registry). Virtual directories, socinfo and DSP libraries stay read-only. The `fwrite` wire layout (one prim word plus the data buffer, two output words) follows the existing `fread` definition and the IDL; it is Inference until a device boot shows the ADSP writing.

`hexagonrpc-0002-sscregistrygen-skip-invalid-json.patch`: the upstream registry generator dereferenced NULL on a truncated vendor JSON (section 4).

## 3. Units, rules, permissions (Verified: installed in scratch root; behaviour Unknown)

| File (package `sp11-sensors`) | Role |
|:--|:--|
| `hexagonrpcd-sensors.service` | `hexagonrpcd -f /dev/fastrpc-adsp -d adsp -s -R /usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11`; `After=`/`BindsTo=dev-fastrpc\x2dadsp.device`; `ConditionFirmware=device-tree-compatible(qcom,x1e80100)`; `ConditionPathExists=` the staged `sns_reg.conf` (silent no-op on the public image); `User=hexagonrpcd Group=fastrpc`; `StateDirectory=hexagonrpcd hexagonrpcd/registry`; `DeviceAllow=/dev/fastrpc-adsp rw` with `DevicePolicy=closed`; `ProtectSystem=strict`; `Restart=always`. Never touches a remoteproc. |
| `hexagonrpcd-sensors-sleep.service` | The suspend/resume hook with the corrected condition: `ConditionFirmware=device-tree-compatible(qcom,x1e80100)` (the Debian hooks used `qcom,sdm670` and never ran; power-thermal V5/V14). One unit: `ExecStart` stops the daemon before `sleep.target`, `ExecStop` starts it after wake-up. Fedora has no `hexagonrpcd-suspend/resume` units, so the Ubuntu drop-in `hexagonrpcd-condition-override.conf` has nothing to override and is not shipped. |
| `iio-sensor-proxy.service.d/10-sp11-sensors.conf` | `After=`/`Wants=hexagonrpcd-sensors.service` |
| `61-sp11-fastrpc-adsp.rules` | `/dev/fastrpc-adsp` `GROUP=fastrpc MODE=0660` (Fedora's `60-fastrpc.rules` gives root:fastrpc 0640; never 0666) |
| `81-sp11-iio-sensor-proxy-ssc.rules` | adds `ssc-accel` to `IIO_SENSOR_PROXY_TYPE` on the ADSP node (3.9 enables only light and compass); proximity stays off |
| `50-sp11-sensors.preset` | enables both units |

Design decisions that differ from the earlier plan:

- **Do not mask `adsprpcd*.service`.** The plan said to mask both because "both claim the ADSP listener". `hexagonrpcd -s` attaches to the sensors PD; `adsprpcd` serves the root PD and `adsprpcd audiopd` the audio PD, all through the same node. Masking `adsprpcd_audiopd` risks audio. Inference (kernel PD attach model and the unit descriptions); **Unknown** until a boot shows the three listeners coexisting.
- **No `sensors-platform-info.service`.** Upstream hexagonrpcd serves `<root>/socinfo/` as `/sys/devices/soc0` and `<root>/sensors/sns_reg.conf` as `/vendor/etc/sensors/sns_reg_config` (`hexagonrpcd/rpcd_builder.c:111-196`). The reference rewrote `sns_reg.conf` to point at `/run/sensors-platform`, which hexagonrpcd's virtual tree cannot serve; it worked there only because the registry was pre-parsed. The staged tree now has `socinfo/` and an unmodified `sns_reg.conf` (Windows maps the same six files to `\sys\devices\soc0\*`, INF lines 553-575).
- The registry is writable state in `/var/lib/hexagonrpcd/registry`, reached through the symlink `<root>/sensors/registry`; `/usr` stays read-only.
- Unit start time: the reference starts early in `sysinit.target` (~6 s). This unit is `multi-user.target` and waits for the device unit. Whether the SNS framework needs the registry served by a given moment (the reference calls the boot "timing-critical") is Unknown; if sensors only appear when the daemon is early, change `WantedBy`/`DefaultDependencies` (device test).

## 4. Registry: can the ADSP generate defaults, and what is needed

### 4.1 Findings

1. **Verified**: upstream `hexagonrpc` contains `tools/sscregistrygen.c` (Richard Acayan, GPL-3.0+), a host-side generator that turns the vendor JSON configuration into the registry files: one file per top-level group, one per nested key starting with `.`, recursively; platform filter `-p hw_platform -s soc_id`; written as plain JSON. It was built (now installed by our `hexagonrpcd` RPM) and run on the Windows package. The reference's claim that a pre-parsed Windows registry or an Android `oemconfig.so` is required is therefore not the only path: the registry can be generated from `sources/windows` alone.
2. **Verified**: with `-p CRD -s 615` the tool produces **293 files** (298 if the truncated `tmd2755.json` is repaired). The reference's registry has 321 files, of which three are state files that are not derived from JSON (`sns_reg_config` 4 KB, `sns_secure_database.bin` 36 KB, `parsed_file_list.csv`), leaving 318. The remaining gap (25 to 20 files) is **Unknown**; candidates are groups the ADSP creates itself, a different file set or filter on their side, calibration/runtime files. The count and naming scale agree (62 groups, 111 first-level dotted children, deeper nesting), which supports the format; it does not prove byte equality.
3. **Verified**: the Windows `qcSensors.dll` (SHA-256 `7bb1e9571bd5838b32ede7ae22810fb377b3bc1354dc0e2a4f8ec497aaaa9fbf`, `sources/windows/rea-evidence/sensors/`) contains the two paths `/Qualcomm/fastRPC/vendor/etc/sensors/config` and `/Qualcomm/fastRPC/persist/sensors/registry/registry`: the host side serves a **writable** registry directory under DriverData, and no pre-parsed registry exists in the driver package. So on Windows the registry is created at run time by the ADSP from `sns_reg_config` plus the JSON files. Together with the REA finding in `2026-10-31-rea-registry.md` section 2.4 (parser compiled into `qcadsp8380.mbn`; single reader, not re-verified here) this makes **ADSP self-generation the Qualcomm-native path**, and it needs exactly the write support that the stock daemon lacks and our patch adds.
4. **Inference**: the reference's custom hexagonrpcd gave write support, and its authors still copied a registry; they report "Could not open oemconfig.so" as non-fatal. Nothing we hold shows they tried an empty registry with write support working. Unknown whether the ADSP creates the registry when the files are served this way; one device boot answers it.

### 4.2 Plan (two independent routes, both staged)

| Route | What the stage script does | Needs |
|:--|:--|:--|
| A, seed (default) | `sp11-sensors-stage.sh` runs `sscregistrygen` per JSON in `json.lst` order (deterministic overwrites) and stages 293 files in `registry-seed/`; `sp11-sensors-install-private.sh --registry seed` copies them into `/var/lib/hexagonrpcd/registry` when empty | works with a read-only daemon; the three ADSP state files are still created by the ADSP (needs the write patch) or absent |
| B, ADSP generates | `--registry empty` (or stage `--no-seed`) | the patched daemon; first boot creates the registry |
| C, real registry | `--registry-from DIR` (a captured Windows `...\persist\sensors\registry\registry`) | not available: the dump has no `DriverData` (listing verified in the integration plan) |

Test order on the device: boot A; if no sensor appears in `ssccli`/`monitor-sensor`, empty the state directory, switch to B (`--registry empty` or delete files), reboot (never reset the ADSP).

### 4.3 Files required per sensor (config directory names; registry groups; counts from `sensors-registry-map.py`, CRD, soc 615)

Names only; no values are recorded. "Identity" means the six `socinfo` files and `sns_reg.conf`, required by all rows. Groups defined by two files overwrite each other (generator, last in `json.lst` wins): `lsm6dso_0_platform`, `lsm6dsv_0`, `lsm6dsv_1`, `qsh_ble_config`, `sns_amd`, `sns_cm`, `sns_tilt`. Total before overwrites 311.

| Sensor (reference status) | JSON files | Registry groups (files) | Notes |
|:--|:--|:--|:--|
| Accelerometer, gyroscope, display side (working) | `8380_crd_lsm6dsv_display.json`, `lsm6dsv_0.json`, `lsm6dsv_0_16g.json` | `lsm6dsv_0_platform` (18), `lsm6dsv_0` (9, overridden by the 3 of the 16g file) | LSM6DSV, `bus_type 3`, bus instance 2, slave 106 (INT values; reference calls it SPI: Inference). Shared: `8380_irq.json` (`sns_irq`), `8380_power_0.json` (`power`), `sns_dae.json` (`dae`), `default_sensors.json` (`default_sensors`, 40) |
| Accelerometer, gyroscope, keyboard side | `8380_crd_lsm6dsv_keyboard.json`, `lsm6dsv_1.json`, `lsm6dsv_1_16g.json` | `lsm6dsv_1_platform` (18), `lsm6dsv_1` | bus instance 1; data only with the Type Cover attached (Inference, S4 open) |
| Calibration | `sns_surface_calibration_accel.json`, `sns_surface_calibration_gyro.json`, `sns_surface_calibration_configuration.json`, `sns_gyro_cal.json` | `lsm6dso_0_platform` (5 each, same group), `surface_configuration`, `sns_gyro_cal_config` | The calibration JSONs target group **`lsm6dso_0_platform`**, not `lsm6dsv_*`, and the two overwrite each other in the generator. Either they are no-ops on this chip or the ADSP maps by family: Unknown. Factory calibration values themselves are not in the package. |
| Magnetometer / compass (working) | `8380_crd_ak991x_display.json`, `ak991x_dri_0.json`; keyboard: `8380_crd_ak991x_keyboard.json`, `ak991x_dri_1.json`; `sns_mag_cal.json` | `ak0991x_0_platform` (11), `ak0991x_0` (4); `ak0991x_1_platform` (11), `ak0991x_1` (4); `sns_mag_cal_config` | AKM AK0991x, `bus_type 0`, instance 4, address 14 |
| Ambient light, colour (light working, colour data) | `8380_crd_tcs3430_0.json`, `sns_surface_color.json`; binary `golden_color_calibration.bin` (in the config directory, opened by the driver, not in `json.lst`) | `tcs3430_0` (3), `tcs3430_0_platform` (8), `sns_surface_color` (2) | `8380_crd_tcs3430_0.json` is listed twice in `json.lst` |
| SAR (data) | `sns_surface_sar.json` | `sar_config` (2) | |
| Gravity, game rotation vector, geomag RV, rotation vector, fast motion | `default_sensors.json` (names `.gravity .game_rv .geomag_rv .fmv .rotv`), `sns_rotv.json`, `sns_geomag_rv.json`, `sns_fmv.json` | `default_sensors` (40), `sns_rotv_platform` (2), `sns_geomag_rv` (2), `sns_fmv_platform` (2) | no JSON for gravity or game_rv beyond `default_sensors` (firmware defaults, Inference) |
| Relative motion, device orientation, motion detect | `sns_rmd.json`, `sns_device_orient.json`, `sns_smd.json`, `sns_amd*.json`, `sns_aont.json`, `sns_tilt*.json` | `sns_rmd` (1), `sns_device_orient_platform` (2), `sns_smd`, `sns_amd`, `sns_aont`, `sns_tilt` | reference: `step_detect`, `tilt`, `amd` open fails; device_orient has no SUID |
| Proximity (reference: no SUID) | `8380_crd_tmd2755.json`, `tmd2755.json` | `tmd2755_0_platform` (12) | **`tmd2755.json` is truncated in the Windows package** (missing closing brace, line 46): not valid JSON; a plausible reason for the missing SUID (Inference) |
| Pressure, hinge angle (reference: no SUID) | `8380_lps22df_0.json`; `stm_lid_angle.json` | `lps22df_0` (5), `lps22df_0_platform` (11); `hingeangle_0_platform` (3) | Windows registers `pressure` and `hinge_angle` in `REGISTERED_SENSORS` |
| Tablet mode | none | none | SSAM KIP switch, not SSC (reference and `hardware/ec-sam`) |
| Framework | `8380_dynamic_sensors.json`, `sns_cm.json`, `disable_mdsp_clients_cm.json`, `sns_diag_filter.json`, `sns_ccd.json`, `sns_dpc.json`, `sns_direct_channel.json`, `sns_distance_bound.json`, `sns_transport_ppe.json`, `qsh_*.json`, camera `.pb` | one to six groups each | needed by the framework; not sensor-specific |

Missing or not derivable from `sources/windows`: (1) the three ADSP state files (`sns_reg_config`, `sns_secure_database.bin`, `parsed_file_list.csv`), which the ADSP writes; (2) any factory calibration or learned values (`.fac_cal` groups hold defaults from the JSON); (3) the 20 to 25 files of the reference registry that this generator does not produce (cause Unknown); (4) a valid `tmd2755.json`. Windows config files outside `json.lst` but in the package (`sns_cal.json`, `lsm6dso_0.json`) are staged because the ADSP may open any name under the config directory (the live registry mapping list has 79 entries).

Staged (Verified, private): `out/firmware-private/sensors/` (owner: user; never git, never the public ISO, S5): `sensors/config/` 70 files, `sensors/sns_reg.conf`, `socinfo/` 6 files, `registry-seed/` 293 files, `SHA256SUMS` (370 lines). Identity values read from the package files: `hw_platform=CRD`, `soc_id=615`, `revision=3.1`, `platform_subtype=Unknown`, `platform_subtype_id=0`, `platform_version=65536`. The reference used `soc_id 555`, revision `2.1`; the JSON filters accept `555, 615, 616, 635`; `sp11-sensors-stage.sh --soc-id 555 --revision 2.1` stages the reference's identity as a fallback (S5 open).

## 5. Test and collector (read-only; written, syntax-checked, not run on a device)

- `/usr/libexec/sp11/sp11-sensors-test [SECONDS]` (opt-in, package `sp11-sensors`; source `hardware/sensors/userspace/sp11-sensors-test`): remoteproc states, node mode (fails on 0666), QRTR service count, served-tree counts, daemon state and refusal counts, `ssccli` line counts for accelerometer/gyroscope/magnetometer/light/compass, `iio-sensor-proxy` state and **masked** `monitor-sensor` output (numbers replaced by `N`, aggregated with counts), and the SSAM tablet switch state by `EVIOCGSW` on the input device named "...Tablet Mode Switch" (kernel name from `surface_aggregator_tabletsw.c:303`). Exit 0 only if the proxy reports an accelerometer, orientation output and an ambient light sensor. It never starts or stops a unit and never writes outside `/tmp`.
- Collector drop-in `/etc/sp11-log-collector.d/sensors.sh` (`hardware/sensors/userspace/collector/sensors.sh`, format of `image/overlay/etc/sp11-log-collector.d/*.sh`, output `extra-sensors.txt`): package versions, nodes, remoteproc, unit states and restart counts, served-tree counts and names, QRTR service list, daemon and proxy journals, dmesg lines, masked `monitor-sensor` counts, tablet switch capability. No raw values.
- Verified here only: `bash -n`; the EVIOCGSW request number `0x8000451b | len << 16`.

## 6. Image request list (see README "Requests")

Packages (from `out/rpms-local/`, a local repo in the image build; they replace Fedora's `iio-sensor-proxy-3.8`): `hexagonrpcd`, `libssc`, `libssc-tools`, `iio-sensor-proxy` 3.9, `sp11-sensors`; already present: `fastrpc`, `fastrpc-services`, `qrtr`. `libssc-devel` and debug RPMs are not needed.

Units and rules: `hexagonrpcd-sensors.service` (enabled by preset), `hexagonrpcd-sensors-sleep.service` (enabled by preset; disable if a suspend test misbehaves), `iio-sensor-proxy.service` (static), udev `61-`, `81-`; do not mask `adsprpcd*`.

Private files (`--private` only, S5): run `sp11-sensors-stage.sh --windows sources/windows --out out/firmware-private/sensors` (done once here), then `sp11-sensors-install-private.sh --stage out/firmware-private/sensors --root <rootfs> [--registry seed|empty]` (replaces the old 78-file stage layout: new tree is `sensors/` + `socinfo/` under the Surface-Pro-11 root).

L0 assertions (static, on the built image): packages present at the pinned NEVRAs; `iio-sensor-proxy` binary contains `ssc-accel`; `hexagonrpcd-sensors.service` has `-s` and `User=hexagonrpcd`; `/usr/lib/udev/rules.d/61-sp11-fastrpc-adsp.rules` has `MODE="0660"` and no `0666` anywhere in `/usr/lib/udev` or `/etc/udev`; `adsprpcd*.service` not masked; user `hexagonrpcd` is in `fastrpc`; public ISO: no `qcom/x1e80100/Microsoft` tree, no `registry` files, no `.json` sensor config; private ISO: 70 config files, 6 identity files, `sns_reg.conf`, symlink `sensors/registry -> /var/lib/hexagonrpcd/registry`, SHA-256 match with `out/firmware-private/sensors/SHA256SUMS`; `/etc/sp11-log-collector.d/sensors.sh` present.

## 7. Verified, Inference, Unknown

**Verified**: the three pins (API and hash); iio-sensor-proxy 3.9 has SSC and MR 381 merged; upstream hexagonrpcd is read-only and lacks methods 0, 5, 23, 24; method numbering matches the IDL; the patched hexagonrpcd builds and passes its tests including a write test; `sscregistrygen` exists and, built, produces 293 files from the package; the truncated `tmd2755.json`; Windows serves a writable registry directory; the six identity values; five RPMs build, lint and install in a scratch root with the expected files, user, preset, D-Bus and polkit policy; the RPMs hold no Windows material.

**Inference**: the `fwrite` wire layout; `hexagonrpcd -s` coexisting with `adsprpcd`/`audiopd`; socinfo-directory identity instead of the reference's `/run` paths; the 293-file registry being what the ADSP expects; the calibration groups being no-ops; sleep-hook benefit; keyboard-side sensors needing the cover.

**Unknown, only the device can verify**: that the ADSP finds the served config and creates or accepts the registry (Route A or B); that 293 seed files are sufficient (reference 318); that sensors initialise when the daemon starts at `multi-user.target` rather than `sysinit.target`; that `User=hexagonrpcd` with `0660` can use the node and that `StateDirectory=` re-owns the seeded files; that `iio-sensor-proxy` finds the SSC service and the accelerometer driver picks the display-side chip and mount matrix; auto-rotation and ALS acceptance (ALS brightness also needs the backlight owner); tablet-mode events; suspend/resume behaviour with the sleep unit; whether the reference's colour/SAR/gravity/rotation sensors read with libssc 0.4.4 alone.

## 8. Corrections to earlier evidence

- `2026-10-31-sensors-integration.md` section 1 lists `platform_subtype_id=65536`, `platform_version=3.1`, `revision=0` (and the rea-registry file `soc_id 615, platform_version 3.1`): the files in the package say `platform_subtype_id=0`, `platform_version=65536`, `revision=3.1` (read from `surfacepro_snscfgcrd8380.../` and mapped one to one by the INF).
- Section 5 and 7 there ("mask `adsprpcd*.service`", "`sensors-platform-info.service`", "hexagonrpcd runs as root or fastrpc"): superseded by section 3 above.
- `2026-10-31-rea-registry.md` 2.2 says "65 active JSON files": `json.lst` has 65 lines but 64 distinct names (`8380_crd_tcs3430_0.json` twice); and one of them (`tmd2755.json`) is not valid JSON.

## 9. Request for `sources/sources.toml` (sources worker; copy of `userspace/rpm/pins.toml`)

```toml
[hexagonrpcd]
version = "0.5.0"
archive_url = "https://github.com/linux-msm/hexagonrpc/archive/refs/tags/v0.5.0.tar.gz"
archive_sha256 = "2173985932ab68d8ac593f9954357123bdbbbe9ba5f1b17a098d9cbcec22c5d5"
upstream_commit = "435ed1cd68e20f8a9fe4871233ed1f8ce7ccf9e8"

[libssc]
version = "0.4.4"
archive_url = "https://codeberg.org/DylanVanAssche/libssc/archive/v0.4.4.tar.gz"
archive_sha256 = "716d6bd6b34d2d753060c6b54c9a87e34fae75b724c763bf9ef487efa3621587"
upstream_commit = "0cf77b93b55752da34dca2dcecc06fca8665184b"

[iio-sensor-proxy]
version = "3.9"
archive_url = "https://gitlab.freedesktop.org/hadess/iio-sensor-proxy/-/archive/3.9/iio-sensor-proxy-3.9.tar.bz2"
archive_sha256 = "19a4ae99b1b8af603fc789841025f9747bf445418d69ec7389e75adb6c8186bf"
upstream_commit = "0085ddf8ecb173a1c5fcf2344aa40e561125354f"
```

Until those tables exist, `build-sensors-rpms.sh` uses `rpm/pins.toml` and prints that the pins are provisional.
