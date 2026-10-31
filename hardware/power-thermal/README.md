# power-thermal

## 1. Summary

Temperature sensors, Windows thermal limits and policies, fuel-gauge battery current limiting, suspend. Linux 7.3 has 58 tsens/PMIC zones with critical-only CPU trips and no cpufreq (not registered in M13); Windows ACPI trip defaults are now extracted; suspend has a Fedora-native opt-in ladder and a cpuidle safety net. Status: `survey` (design and read-only tooling written, nothing run on the device). Evidence: [suspend, thermal and battery](evidence/2026-10-31-suspend-thermal.md); plan: [test-plan.md](test-plan.md).

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C5A/0C58/0C59/0C91/0CBF/0D01 (temperature)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C5E..0C64 (ADC TM)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CF2..0CF6 (CPU parking/DCVS)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C77 (FGBCL)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C11 (ADC)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_06E5 (subsystem thermal)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_MSHW&DEV_0187/0188 (Surface thermal)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcpep.wd8380` | PEP: ACPI thermal zones `TZ1/TZ3/TZ5/TZ15-TZ24` name it as their `_TZD`; limits tables unread (REA Q-R2) |
| `qcadc8380` | ADC and ADC thermal-monitor devices (`QCOM0C11`, `QCOM0C5E-0C64`); not opened |
| `qcfgbcl8380` | Fuel-gauge battery current limiting (`QCOM0C77`): live values `BCLCapability 7`, `OCPCurrent 17000` mA, levels at 85 and 88 percent; Verified from INF and registry |
| `qcfgbclext8380` | Extension INF of the FGBCL device; not opened |
| `qcsubsysthermalmgr` | Subsystem (DSP) thermal manager (`QCOM06E5`); tables unread (REA Q-R2) |
| `mstemperaturesensor` | Microsoft temperature sensor driver (`MSTemperatureSensor.sys`, ARM64 code); role by name only |
| `surfacethermalpolicy` | Surface Thermal Policy driver, ACPI `MSHW0187` (`\TPOL`); policy content unread (REA Q-R3). The nine `MSHW0188` zone sensors are the SMF client |
| `surfacepowermeterdriver` | Power meter; not opened |
| `surfacepowertrackercore` | Power tracker; not opened |

## 4. Linux 7.3

- Driver: `thermal/qcom/tsens`
- Driver: `thermal/qcom/lmh`
- Driver: `iio/adc/qcom-spmi-adc5-gen3`
- Driver: `cpuidle-psci`
- Driver: `qcom-pdc`
- DT: `hamoa.dtsi thermal-zones`
- DT: `hamoa.dtsi:9099-` 58 thermal zones: CPU and CPUSS critical 115 C only, GPU passive 95 / critical 115 with cooling maps, others hot 90 / critical 115; no LMh node.
- Idle: `hamoa.dtsi:278-313` (`cpu-sleep-0`, CL4, CL5, SS3); `cpuidle-psci.c` s2idle path (domain logic rides on the last cpuidle state).
- Suspend: `drivers/platform/surface/aggregator/core.c:410-505` (display-off at prepare, D0-exit, D0-entry); `gpio-keys` lid wake; `pmic_pwrkey` wake; RTC alarm owned by ADSP.
- Native coverage: **partial**. M13 (private logs): cpuidle works on 10 CPUs, clusters 1 and 2 reach CL5, **cpufreq not registered**, no CPU cooling, only `PCIe_Port_Link_Speed` and `ath12k_thermal` cooling devices.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Windows trip points and limits not mapped to Linux zones | ACPI defaults extracted (evidence 5.2); Linux values at or below them listed (5.3); sensor-to-zone mapping needs REA Q-R1; no patch until cpufreq exists |
| cpufreq not registered (scmi_cpufreq not loaded in M13), no CPU cooling | soc-boot and image: find why; then one DT patch adds cooling maps and lower passive/critical trips |
| fan control path (SAM) | No ACPI fan methods (Verified); EC regulates; Linux reads RPM only (ec-sam 0003); no write path added (S6) |
| s2idle correctness | Opt-in ladder `sp11.suspend_diag=1..4`, cpuidle guard as default-on safety net; result decides whether the Ubuntu `cpu-sleep-0` workaround is needed |
| s2idle wake sources | Lid and power button are wake sources by DT/driver; Type Cover and others off by default; wake policy unit; untested (lid IRQ count 0 in M13) |
| BCL | Windows FGBCL values recorded (OCP 17 A, levels 85/88 percent); Linux has no handler and no LMh node; nothing to raise (S6); a Linux handler is a later question |
| charge limit / battery health | D23 confirmed (single SAM battery, no `charge_control_*`); Windows battery-health options Unknown, Windows read-only pass requested |
| SAM D0-exit/entry and Type Cover | Suspend performs the round trip the shutdown path lacks; the `devices` rung is a no-reboot experiment for ec-sam |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Windows trip points and mitigations per zone | Verified (static ACPI defaults: passive 104.85 C on TZ1/TZ3/TZ5/TZ99, critical 114.85 C CPU/SoC, GPU critical 109.85 C); Unknown (effective run-time values, sensor mapping) | REA Q-R1, Q-R2 in the evidence |
| Q2 | Fan control: SAM or ACPI fan? | Verified: ACPI `FAN0` has only `_STA`; EC-managed, Linux reads RPM through SAM. Unknown: RPM validity, whether the EC needs host temperatures | `ssam-ro.py fan-rpm` and hwmon after ec-sam 0003; REA Q-R3 |
| Q3 | s2idle wake sources and power draw | Verified (DT/driver wake sources); Unknown (behaviour on the device) | Ladder rungs and wake tests, test-plan sections 1-2 |
| Q4 | Do we need the Ubuntu `cpu-sleep-0` workaround? | Inference: parity DT avoids the SS3 request, untested | Ladder rungs `real-guard` and `real-noguard` |
| Q5 | Why is `scmi_cpufreq` not loaded? | Unknown | `modprobe`/udev modalias check on the next boot (soc-boot, image) |
| Q6 | Windows battery-health options | Unknown | Read-only Windows pass; REA Q-R4 |

## 7. Acceptance

1. Sustained load stays below Windows limits (risk S6); every Linux trip is at or below the Windows value
2. s2idle enters and wakes from lid and power button; keyboard, touchpad, panel and backlight return; `suspend_stats` fail stays 0
3. cpufreq registered on three clusters; CPU passive trips engage below 104 C
4. Single SAM battery, no writable charge control (D23)

## 8. Requests

- **kernel:** keep `CONFIG_PM_DEBUG=y` and `CONFIG_PM_SLEEP_DEBUG=y`; no patch is requested now. Later: a DTB variant that re-adds SS3 (inverse of soc-boot parity) for a controlled experiment, only after `real-noguard` passes.
- **image:** install `userspace/overlay/` as is and `collector/power-thermal.sh` as `/etc/sp11-log-collector.d/power-thermal.sh`; enable the units in the preset (they test the kernel line); add menu entries "SP11 debug, suspend ladder 1" (`mem_sleep_default=s2idle no_console_suspend pm_debug_messages sp11.suspend_diag=1`) and, marked risky, levels 2 and 3; add a lock-free `sp11-log-collector publish-extra` subcommand (R-I2); find out why `scmi_cpufreq` did not load in M13.
- **soc-boot:** explain the missing cpufreq registration (acceptance item); confirm that system domain without SS3 is intended; own the later SS3 experiment.
- **ec-sam:** never combine `sp11.suspend_diag` and a `sp11.ssam_*` shutdown-mode cycle in one boot; treat the `devices` rung as the no-reboot D0-exit/D0-entry test; read `surface_fan`/`surface_temp` hwmon values from the new collector.
- **dsp-subsystems:** review the ladder's remoteproc and wake IRQ observations; decide whether a CDSP-stop arm is acceptable if a CDSP wake or hang appears.
- **display-lcd:** the ladder records eDP and backlight state around each rung (evidence only).
- **sensors:** if `hexagonrpcd` is packaged, apply `ConditionFirmware=device-tree-compatible(qcom,x1e80100)` to its suspend/resume units.
- **gpu, npu:** limits stay at or below Windows; the GPU proposals in evidence 5.3 apply when the GPU is on.
- **sources (REA, later):** Q-R1 to Q-R5 in the evidence section 7; Windows read-only battery-health pass (Q-R4).

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-31: reviewed the Ubuntu SP11 suspend fix against our parity DT and M13; extracted Windows ACPI thermal defaults and FGBCL values; wrote the opt-in suspend ladder, cpuidle guard, sleep/logind drop-ins, read-only collector and thermal sampler (nothing run on the device, nothing built); found cpufreq not registered in M13. No patch written (mapping Inference, no cooling device).
