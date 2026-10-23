# power-thermal

## 1. Summary

Temperature sensors, Windows thermal limits and policies, fuel-gauge battery current limiting, suspend. Linux 7.3 has TSENS and LMh; the Windows trip points and the SAM fan path are not mapped. Status: `survey`.

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
| `qcpep.wd8380` | TBD |
| `qcadc8380` | TBD |
| `qcfgbcl8380` | TBD |
| `qcfgbclext8380` | TBD |
| `qcsubsysthermalmgr` | TBD |
| `mstemperaturesensor` | TBD |
| `surfacethermalpolicy` | TBD |
| `surfacepowermeterdriver` | TBD |
| `surfacepowertrackercore` | TBD |

## 4. Linux 7.3

- Driver: `thermal/qcom/tsens`
- Driver: `thermal/qcom/lmh`
- Driver: `iio/adc/qcom-spmi-adc5-gen3`
- Driver: `cpuidle-psci`
- Driver: `qcom-pdc`
- DT: `hamoa.dtsi thermal-zones`
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Windows trip points and limits not mapped to Linux zones | TBD |
| fan control path (SAM) | TBD |
| s2idle wake sources | TBD |
| BCL | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Windows trip points and mitigations per zone | TBD | REA of `qcpep8380.sys` policies; `surfacethermalpolicy` and SMF clients |
| Q2 | Fan control: SAM or ACPI fan? | TBD | `surfacesam`, SMF fan client REA |
| Q3 | s2idle wake sources and power draw | TBD | Device tests in phase 4 |

## 7. Acceptance

1. Sustained load stays below Windows limits (risk S6)
2. s2idle enters and wakes from lid and power button

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
