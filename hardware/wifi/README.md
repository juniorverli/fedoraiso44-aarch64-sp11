# wifi

## 1. Summary

Qualcomm WCN7850 Wi-Fi 7 on PCIe4, handled by `ath12k`. Linux 7.3 has the driver and the DT node with its power sequencer. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `PCI\VEN_17CB&DEV_1107` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CD5 (WLAN thermal)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CFC (WLAN limits)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcwlanhmt8380` | TBD |
| `qcwlanhmt_ext8380` | TBD |
| `surfacesarmanager` | TBD |
| `surfaceradiotelemetrydriver` | TBD |

## 4. Linux 7.3

- Driver: `net/wireless/ath/ath12k`
- Driver: `power/sequencing pwrseq-qcom-wcn`
- DT: `x1-microsoft-denali.dtsi &pcie4_port0 wifi@0 (pci17cb,1107), wcn7850-pmu`
- Native coverage: **full** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| board data file selection (Fedora board-2.bin vs Windows bdwlan_*.elf) | TBD |
| SAR / regulatory power tables | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which board data does ath12k pick for this board, and does it match the Windows `bdwlan` variant for this SKU? | TBD | `dmesg` board name on the device; INF registry values selecting `bdwlan_*.elf` |
| Q2 | SAR and regulatory tables | TBD | `surfacesarmanager` REA; ACPI SAR methods |

## 7. Acceptance

1. Connects to 2.4/5/6 GHz networks; throughput sane; survives suspend in phase 4

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
