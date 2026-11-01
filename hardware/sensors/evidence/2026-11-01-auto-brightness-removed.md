# Automatic brightness removed; the ALS remains present and is diagnostic only

- Date: 2026-11-01
- Component: `hardware/sensors`
- Decision owner: operator (relayed by the orchestrator)
- Scope: acceptance criteria and device test plan. No hardware fact is changed.

## 1. Decision

Automatic brightness is removed from this component. It is no longer a requirement, a test expectation, or an acceptance gate. Ambient-light readings stay available for diagnostics only.

The operator's rationale was that the ambient-light sensor does not exist in Windows and that the automatic-brightness path was invented in our code. The decision is implemented here as given; the two supporting claims are graded below against the repository's evidence. They are not supported: the sensor is reported present by Windows, and the response path is upstream software, not code written by this project.

## 2. Counter-evidence: the ambient-light sensor exists

| # | Statement | Grade | Evidence |
|:--|:--|:--|:--|
| E1 | Windows reports an ambient light sensor on this unit | Verified | `sources/windows/live-inventory/sensors/winrt-sensors.txt` (SHA-256 `ed1eaf6dc98bcc1ef28f4536f8057454865848cc3dc4ced77d53bd7707b7c6b7`): `LightSensor: PRESENT id=\\?\ACPI#MSHW048A#2&daba3ff&0#...\ minInterval=250` |
| E2 | The board's CRD sensor configuration defines a TCS3430 light/colour sensor | Verified | `sources/windows/DriverStore/surfacepro_snscfgcrd8380.inf_arm64_f5d7e051fecc22c3/8380_crd_tcs3430_0.json` (SHA-256 `68c98cfd3a5533b828ac67bc067933a0c3fd449690c5a8341c2e5f21413a4f15`), top-level groups `config`, `tcs3430_0`, `tcs3430_0_platform`; registry groups recorded in `2026-10-31-sensors-build.md` section 4.3 |
| E3 | Windows ships an ambient-light sensor driver package | Verified | `sources/windows/DriverStore/sensorsalsdriver.inf_arm64_39e5b8101dd9decb/`: `sensorsalsdriver.inf` SHA-256 `a25b64aa23ba2af1c352291d25ac8eb29c3fbf4ca9102e8510f267add9b76a2d`, `SensorsAlsDriver.dll` `7ebf748ff8bd0a13eaf899ff42df2d79fa5455057397548b1dc5372c00cd3d73`, `acpials.sys` `f89f86daee438d488b13ef95880f569b908da068983aa97be1a5bc3c22f359af` |
| E4 | The INF in E3 binds the generic ACPI ambient-light device `ACPI\ACPI0008` | Verified | `sensorsalsdriver.inf`: `%SensorsAlsDriver.DeviceDesc% = SensorsAlsDriver_Install,ACPI\ACPI0008` |
| E5 | `ACPI0008` is enumerated on this unit | TBD | Not present in `sources/windows/live-inventory/pnp-present.json`. This does not weaken E1: the WinRT light sensor is exposed through `MSHW048A` (the ADSP/SSC path), not necessarily through `ACPI0008` |
| E6 | The reference Linux stack reads light and colour from the AMS TCS3430 on this board | Inference | `2026-10-31-sensors-integration.md` line 14 ("light and colour (AMS TCS3430)" give data) and `2026-10-31-sensors-build.md` section 4.3 ("light working, colour data"); these restate the reference project's status, not a measurement made here |
| E7 | The physical ALS exists on this unit | Inference (strong) | E1 (Windows enumerates a light sensor) + E2 (board config names the TCS3430) + E3/E4 (Windows ships its ALS driver); no teardown or board photo in `sources/` |
| E8 | "The ambient-light sensor does not exist in Windows" | Refuted | Contradicts E1, E2 and E3, all Verified. The premise is not a hardware finding of this repository |
| E9 | "The automatic-brightness path was invented in our code" | Not supported | The response is upstream: GNOME's `org.gnome.settings-daemon.plugins.power ambient-enabled` key and iio-sensor-proxy 3.9's `src/drv-ssc-light.c` (upstream source facts in `2026-10-31-sensors-build.md` lines 11-13). This component's code publishes the light sensor; it contains no backlight logic. What this project added was the earlier acceptance criterion, which is what is removed |

E1 is the decisive fact: a Windows-rendered inventory run on this unit lists `LightSensor: PRESENT` on the exact SSC device node (`MSHW048A`) that this component serves. The sensor exists even though its automatic-brightness use does not.

## 3. Mechanism of the removal (image owner's files)

Verified from image commit `2ee4dbf` (`image: prepare M16 image with GPU firmware in initramfs, speaker UCM for safe/debug, and auto-brightness disabled`):

- `image/kiwi/overlay/root/etc/dconf/db/distro.d/92-sp11-display` contains:

  ```ini
  # SP11 display defaults: disable automatic brightness adjustment from ambient light sensor / front camera sensor
  [org/gnome/settings-daemon/plugins/power]
  ambient-enabled=false
  ```

- `image/kiwi/overlay/root/etc/dconf/db/distro.d/locks/92-sp11-display` contains `/org/gnome/settings-daemon/plugins/power/ambient-enabled`, so a user session cannot override the key.

These files belong to the image worker. This dossier references them and does not duplicate or modify them.

| Statement | Grade | Basis |
|:--|:--|:--|
| `ambient-enabled=false` is shipped in the distro dconf profile | Verified | file content at image commit `2ee4dbf` |
| The key is locked | Verified | lock file at image commit `2ee4dbf` |
| A user session cannot re-enable the key | Inference | dconf lock semantics; a device test confirms it |
| The GNOME power plugin is the only consumer that would change the backlight from ALS data | Inference | upstream GNOME behaviour; no other ALS-to-backlight writer found in this repository |

## 4. What a device test would show

The updated `test-plan.md` asks for these observations; each outcome has one interpretation:

1. `gsettings get ... ambient-enabled` prints `false` and `gsettings writable ...` prints `false`: the image mechanism is active.
2. Covering and uncovering the ALS for 30 seconds each, repeated, leaves the backlight unchanged: the removal works. This is the acceptance result.
3. `monitor-sensor` or `ssccli` reports light events: the ALS is readable for diagnostics, consistent with E1-E2. No light events point to a registry/daemon gap (see the open registry questions), not to missing hardware.
4. The backlight changes on cover/uncover: the removal did not take effect (locked key not applied in the session) or another component wrote the backlight. This is an image/session failure, not a sensors pass and not a reason to re-enable the feature.
5. `ambient-enabled` is missing from GSettings: the session or schema is wrong; it does not invalidate the removal and must not be worked around by enabling the key.

## 5. Consequences

- `README.md` acceptance no longer requires an automatic-brightness response; it requires that brightness not change.
- `test-plan.md` treats light readings as optional diagnostics and measures the absence of a brightness change.
- The `display-lcd` request for backlight control for ALS auto-brightness is withdrawn.
- `component.toml` records the decision in its gaps list instead of an unmeasured brightness response.
- E1-E3 remain hardware facts. If automatic brightness is ever reconsidered, the sensor is already known to be present and the upstream path already exists; only the dconf key and lock would need to change, by the image owner.
