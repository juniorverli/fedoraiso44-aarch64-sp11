# ec-sam

## 1. Summary

The Surface Aggregator Module (SAM) carries the Type Cover, system battery/AC and posture functions over a 4 Mbaud UART. M5 enumerated the keyboard, touchpad, KIP tablet switch and SAM power supplies; proposed registry changes remove two unsupported HID endpoints, while user interaction and plugged-in charging still need device evidence. Status: `designed`, pending independent cross-check and acceptance captures.

D23 selects SAM `BAT1`/`ADP1` and blacklists `qcom_battmgr` now. D24 applies: changes remain uncommitted for the orchestrator. Detailed hashes, locators, grades and limits are in [M5 evidence](evidence/2026-10-28-m5-device-sam.md); build results are in [validation evidence](evidence/2026-10-28-validation.md).

## 2. Hardware

| Item | Value and grade | Source |
|:--|:--|:--|
| SAM link | Verified: QUP0 SE2, UART `b88000.serial`, 4,000,000 baud, 8N1, RTS/CTS; wake TLMM GPIO 91 | `sources/windows/live-inventory/acpi/ssdt.dsl:504`; `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1229`; M5 SAM probe |
| Running SAM | Verified: firmware 27.201.139; no firmware write requested | M5 dmesg line 1173 |
| Type Cover | Verified: SSAM KIP TID 2, IIDs 1 keyboard (`045E:09AE`), 3 touchpad/mouse (`045E:09AF`), 5 update HID (`045E:09D4`); these are HID product IDs, not evidence of USB transport | M5; Windows PnP mini-driver PDOs 1/3/5 |
| Failed SAM sensor HID | Verified identity: TC 15/TID 1/IID 6/function 0. Inference: unsupported endpoint on this firmware. Actual sensor platforms are separately represented by `MSHW048A/B` and ADSP dependencies | Linux registry `:134`; Windows DSDT SEN2/SEN3; M5 -71 |
| Failed pen-stash HID | Verified identity: TC 15/TID 2/IID 2/function 0, pen taken/stashed notifications. Inference: unsupported by the attached cover. Pen digitizer is a separate `MSHW0484` device | Linux registry `:200`; Windows PnP; M5 -71 |
| Battery/AC | Verified: SAM BAT1/ADP1 supply discharge state, percentage, energy and AC online=0 on M5. Inference: ADSP supply duplicates the same pack. Windows disables PMBM | M5 power capture; DSDT `:675`; D23 |
| Lid | Verified: TLMM GPIO 2, ACPI reads 1=open; upstream DT has a lid switch | `dsdt.dsl:55516`; Denali DT gpio-keys |
| Volume buttons | Verified from ACPI MSHW0040: PM01 pins 0xD5 and 0xD7, input only, PullUp, ActiveBoth edge, not wake capable, debounce 0; power is TLMM GPIO 19 (SharedAndWake). Inference: PM01 pin = 0xCF + PM8550 GPIO, so GPIO 6 (up, first resource) and GPIO 8 (down); active low; 1.8 V; 15 ms from other DTs. Orientation and polarity need the device test | `evidence/2026-10-31-volume-buttons.md`; patch 0005 (candidate, `sw-ready` after cross-check); `patches/hold/0004-*` stays held (power) |
| Fan candidate | Verified Linux read request: TC 05/TID 1/IID 1/CID 01; ACPI FAN0 depends on SSH. Response on this unit TBD | `sources/linux/drivers/hwmon/surface_fan.c:16`; `ssdt.dsl:2807`; patch 0003 |
| Tablet posture | Verified: KIP tablet switch enumerates. ACPI hotplug feature words are 080e (KIP) and 060c (SAM); their bit meanings are not established by the registry capture | M5; `ssdt.dsl:397`; held patch 0002 |

## 3. Windows

Packages below are under `sources/windows/DriverStore/<name>.inf_arm64_*`. Direct evidence is distinguished from inherited leads; no predecessor binary decompilation is promoted to Verified.

| Package | Role |
|:--|:--|
| `surfaceserialhubdriver` 9.167.16.0 | SSH UART transport, `ACPI\MSHW0084` (ACPI/PnP and Linux comparison) |
| `surfacesam` 27.201.139.0 | SAM signed firmware capsule; version agrees with M5; never flash (S3) |
| `surfacehotplug` 3.206.9.0 | Verified INF: KIP `MSHW0153`, SAM HostRegister target; creates the cover child bus |
| `surfacehidminidriver` 3.98.18.0 | Verified INF: generic HID transport for KIP/SAM; multiple-instance IDs enabled. Present children are KIP ordinals 1/3/5 only |
| `surfacebattery` 2.135.6.0 | System Battery-class device through SAM (PnP); Linux `surface_battery` and `surface_charger` |
| `surfacebutton` 4.103.13.0 | Inherited lead: MSHW0040 GPIO buttons → virtual HID; candidate DT patch held |
| `surfacepowerstate` 3.26.7.0 | Inherited lead: SAM power-state notifications; Linux aggregator has its own state handling |
| `surfacetimealarmacpifilter` | Inherited lead: SAM wake-alarm integration; deferred |
| `surfaceacpiplatformextensiondriver` | Inherited lead: MSHW0299 platform extension and FAN0 method handling; no new REA evidence in this session |
| `surfacesystemmanagementframeworkdriver`, `surfacesmfclient`, `surfaceihvcpusmfclient`, `surface.smf.117.0.*` | Inherited leads: thermal/fan/charge policy. Not ported; no limits changed (S6) |
| `surfacetypecoverv7fwupdate`, `surfacecfuoverhid` | Inherited lead plus IID 5 enumeration: cover update support, never write (S3) |
| `surfacetypecoverv7fprudedriver` | Inherited lead: cover fingerprint UDE; no corresponding device in the captured attached-cover tree |

ACPI `PMBM` `_STA` always returns zero. A driver package containing battery-manager code does not mean Windows enabled that device. The SAM and KIP hotplug nodes likewise do not prove that every possible HID child exists.

## 4. Linux 7.3

Paths in this table are relative to `sources/linux/` at the pinned base.

| Piece | Coverage and source |
|:--|:--|
| DT SAM | `arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1229`, `microsoft,surface-sam`; UART2 and GPIO 91 |
| DT transport/platform hub | `drivers/platform/surface/aggregator/core.c:741`, `:826`; creates platform hub on DT |
| Registry | `drivers/platform/surface/surface_aggregator_registry.c:408` (`sp11`), `:513` (`microsoft,denali`); creates fixed software nodes rather than discovering HID endpoints |
| KIP hub | `drivers/platform/surface/surface_aggregator_hub.c:97`, `:293`, `:350`: connection query/events add or remove child clients |
| HID path | `drivers/hid/surface-hid/surface_hid.c:42`, `:233`; `surface_hid_core.c:39` requests a 9-byte descriptor; keyboard ultimately `hid-generic`, touchpad `hid-multitouch` on M5 |
| Battery | `drivers/power/supply/surface_battery.c:446`, `:464`, `:508`: energy-unit properties, charging/discharging/full/not-charging state and percentage. Device `ssam:01:02:01:01:00` |
| AC | `drivers/power/supply/surface_charger.c:41`, `:140`, `:182`: platform power source, ONLINE, Mains type, supplies BAT1/BAT2. Device `ssam:01:02:01:01:01`; module `surface_charger`, SSAM driver name `surface_ac` |
| Battery updates | BAT events and AC events call `power_supply_changed`; AC changes schedule a battery refresh after 5 s (`surface_battery.c:408`) |
| Tablet mode | `drivers/platform/surface/surface_aggregator_tabletsw.c`; base sp11 uses KIP; held patch 0002 proposes POS |
| Initramfs | Must contain UART/serdev dependencies, `surface_aggregator`, `surface_aggregator_registry`, **`surface_aggregator_hub`**, `surface_hid`, `surface_hid_core`, `hid`, `hid_generic` (or built-in equivalents). The hub is a required parent for keyboard enumeration; a transport-only image is insufficient |

LUKS entry and an initramfs emergency shell need the keyboard chain early. `hid_multitouch` is required early if the image promises an initramfs touchpad; it is unnecessary for text passphrase entry and can otherwise load after switch-root. The inspected shipped config has `CONFIG_HID_GENERIC=y`, `CONFIG_SERIAL_QCOM_GENI=y` and `CONFIG_SERIAL_DEV_BUS=y`; these need no `.ko` in the initramfs. The Surface hub and HID transports are modular and do need inclusion. Battery, fan and tablet-switch modules are not dependencies of keyboard enumeration. Dracut must resolve module dependencies and include the UART pinctrl/clock/provider chain already used to bring SAM up at +3.3 s.

The predecessor's initramfs inventory predates M5, so the exact M5 omission is not independently established. Require `lsinitrd` checks and device verification, rather than explaining the +26.5 s keyboard registration by timing alone.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Two optional endpoints fail descriptor loading | Active patch 0001 removes them from the local Denali group; no change to HID validation. Pen-stash deletion is limited by evidence from this attached cover |
| Keyboard may be unavailable before switch-root | R3: force/include the complete keyboard chain in dracut and assert it with `lsinitrd`; verify at `rd.break=pre-mount` |
| Duplicate ADSP system battery | D23 is settled: R4 blacklists `qcom_battmgr` and excludes it from initramfs; UCSI stays. Do not gate this on charger captures |
| Plugged-in UPower behavior not captured | Test each USB-C port and available Surface Connect; verify status, percentage, energy, online and UPower state with SAM only |
| KIP posture may be wrong, particularly after resume | Keep 0002 held; upstream reports the same concern. Compare fixed posture snapshots and read-only POS queries before release |
| Fan RPM not registered | Active candidate 0003 adds existing read-only fan client; valid RPM and cross-check required |
| Volume DT mapping | Active candidate 0005 (volume only, from ACPI plus Linux sources); run `tools/collect-volume-buttons.sh` for orientation/polarity. Power button stays with hold 0004 / existing pmic_pwrkey until the device capture |
| Keyboard backlight, wake alarm | Deferred; outside this delivery |
| Platform profile | Do not add: policy writes require evidence about thermal behavior (S6) |

## 6. Open questions

| ID | Question and grade | Evidence needed |
|:--|:--|:--|
| Q1 | Answered identity; unsupported endpoints are an Inference for this firmware/cover | M5 evidence section 2; retain cover compatibility limitation |
| Q2 | Volume pins reproduced from ACPI (Inference for GPIO 6/8 via the 0xCF offset, I1-I2); up/down and polarity Unknown until the device test | `collect-volume-buttons.sh` phases UP/DOWN; independent cross-check (protocol 5.1); power button path still open |
| Q3 | Keyboard backlight command: TBD | Separate investigation, no firmware writes |
| Q4 | Fan response: TBD | `ssam-ro.py fan-rpm` and hwmon RPM after 0003 |
| Q5 | Fingerprint: not enumerated on captured cover | Revisit only with another cover |
| Q6 | POS source and folded/resumed posture: TBD | Held 0002 test and `ssam-ro.py` posture reads |
| Q7 | SAM charging status and ADP1 on each connector: TBD | Test-plan section 3; never re-enable qcom_battmgr as a workaround |
| Q8 | Real keyboard/touchpad and initramfs operation: TBD | Operator report and capability-only collectors |
| Q9 | Precise cause of late input enumeration: TBD | Next image module inventory and monotonic boot/module logs |

## 7. Acceptance

1. Keyboard/touchpad work attached, after reattachment, and through posture transitions; keyboard is usable at a LUKS prompt or initramfs shell.
2. UPower exposes one system battery, BAT1-derived energy/percentage/status, and ADP1-derived online state. Charger plug/unplug works on each available input without changing firmware limits.
3. Folded/detached/laptop posture and lid state are correct; resume is checked when the image owner enables that test.
4. Power/volume behavior is confirmed only after held DT work is cross-checked; no device-event recording is needed.
5. Candidate patches introduce no SAM errors; removed HID endpoints no longer probe. Enumeration alone is not functional acceptance.

## 8. Requests

- **kernel R1:** review active patches **0001 and 0003** for `kernel/series`; 0001 is a local current-cover fix (sensor removal has an upstream counterpart). Keep **hold/0002 and hold/0004 out**. Arrange protocol §5.1 cross-check before `sw-ready`; this continuation is not the orchestrator-started blind cross-check. No commits were created here.
- **kernel R2:** pin/check `CONFIG_SURFACE_AGGREGATOR_HUB=m`, `CONFIG_SURFACE_AGGREGATOR_TABLET_SWITCH=m`, `CONFIG_SURFACE_AGGREGATOR_CDEV=m`, `CONFIG_SURFACE_HID=m` (selects CORE), `CONFIG_BATTERY_SURFACE=m`, `CONFIG_CHARGER_SURFACE=m`, `CONFIG_SENSORS_SURFACE_FAN=m`, `CONFIG_SENSORS_SURFACE_TEMP=m`, `CONFIG_HID_GENERIC=y`, `CONFIG_HID_MULTITOUCH=m`, and `CONFIG_KEYBOARD_GPIO=m`, or built-in equivalents. Preserve both BTF options. Do not add a performance-profile client.
- **image R3:** use Fedora dracut `add_drivers`/`force_drivers` to ensure the full early keyboard chain above, particularly `surface_aggregator_hub` and `hid_generic`; verify actual image modules with `lsinitrd`, add L0 assertions, and test `rd.break=pre-mount`. Include `hid_multitouch` early only if an initramfs touchpad is promised. Include Fedora `libinput-utils` and `evtest` and stage the three tools under a stable path such as `/usr/libexec/sp11/ec-sam/`.
- **image R4 (D23, immediate):** blacklist `qcom_battmgr` in modprobe configuration, set `rd.driver.blacklist=qcom_battmgr modprobe.blacklist=qcom_battmgr`, omit it from initramfs, prevent explicit image load paths, and fail L0 if it can load or any image helper writes a `charge_control_*` attribute. Keep pmic-glink, UCSI and `ucsi-source-psy-*`. Collect the allowlisted power snapshots in test-plan section 3 with a charger attached; a failed SAM check is a D23 revisit request, never permission to restore writable thresholds.
- **dsp-subsystems R5 / usb-typec R6:** share SAM/UCSI charger observations for each port. Windows PMBM is disabled; no charge/thermal limit writes. Do not defer D23 pending duplicate-pack confirmation.
- **image/display-lcd R7:** inspect the M5 collector oops at `msm_dp_test_active_show`; avoid reading that debugfs file. This is a separate display collector issue; do not paste raw register/address-bearing log lines into git.
- **orchestrator R8:** reproduce/cross-check the held button draft's electrical parameters before release; review upstream POS switch fix against local posture/resume evidence. Sources owner must pin any external patch before adopting it as a new shared input.

- **kernel R9 (helper):** document or add linked-module validation for `kernel-dev.sh module <directory>`: the current directory target produces objects only. A rejected extra-fragment configuration can also leave the prior `.config.sp11-sha` beside a changed `.config`, so retrying the old profile may skip regeneration; invalidate the stamp before changing config. This worker removed only its own generated stamp and used the standard incremental build for final verification.
- **image R10 (2026-10-30, keyboard dead after reboot):** install `collector/ec-sam.sh` as `/etc/sp11-log-collector.d/ec-sam.sh`; add the units in `evidence/2026-10-30-keyboard-reboot.md` section 5 (shutdown unbind, opt-in `sp11.ssam_rebind` GRUB entry) and run the four-step test there. No kernel patch yet.
- **kernel R11 (2026-10-30, Windows transition):** add `patches/0007-*` (`surface_aggregator.shutdown_mode`) to `kernel/series` for the next image; no behaviour change by default. **image R12:** GRUB entries `SP11 debug, SAM shutdown quiet|silent|clean` and the test in `evidence/2026-10-30-windows-transition.md` sections 5-6.
- **kernel R13 (2026-10-31, volume buttons):** add `patches/0005-arm64-dts-qcom-x1p64100-microsoft-denali-Add-the-vol.patch` to `kernel/series` for the next DT build (DT only, LCD board file; applies on the 69-patch series, `CHECK_DTBS` clean); ensure `CONFIG_KEYBOARD_GPIO=m` (R2). **image R14:** stage `tools/collect-volume-buttons.sh` under `/usr/libexec/sp11/ec-sam/` and run the two 10 s phases in `evidence/2026-10-31-volume-buttons.md` (operator presses up, then down). Orchestrator: protocol 5.1 cross-check of the pin mapping (I1) before `sw-ready`.

## 9. Log

- 2026-10-23: dossier created from static survey.
- 2026-10-28: Claude draft added M5 evidence, candidate patches 0001–0004 and SSAM read tool; interrupted during build.
- 2026-10-28: Codex continuation (D24): corrected endpoint evidence grades and cover scope, applied D23 without a charger gate, documented complete early keyboard path, added private-data-minimized capability/power collectors and UPower charging checks, held insufficiently sourced button DT candidate, and recorded actual validation results. Status remains `designed`; all changes uncommitted.
- 2026-10-30: M10 keyboard-after-reboot report investigated; logs show normal enumeration, cause Unknown; collector and image mitigation proposed (evidence `2026-10-30-keyboard-reboot.md`).
- 2026-10-30: operator reports keyboard freeze at the start of Windows after a Linux session; shutdown source analysis, patch 0007 (`shutdown_mode`) and test plan in `evidence/2026-10-30-windows-transition.md`. Not built.
- 2026-10-31: volume buttons: MSHW0040 resources decoded from DSDT/SSDT (evidence `2026-10-31-volume-buttons.md`), PM01 to PM8550 GPIO offset derived, patch 0005 (volume only) validated with `CHECK_DTBS`; device test added. Not built into an image.
