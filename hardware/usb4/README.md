# usb4

## 1. Summary

The USB4 host router and its PCIe/DP tunnels. Linux has no Qualcomm USB4 host router glue. Docks and Thunderbolt devices need this; plain USB-C and DP Alt Mode do not. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C6D (USB4 host router bus)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcusb4bus8380` | TBD |
| `qcusb4filter8380` | TBD |
| `surfaceusb4dockfwupdate` | TBD |
| `surfacethunderbolt4dockfwupdate` | TBD |
| `surfacedock2fwupdate` | TBD |

## 4. Linux 7.3

- Driver: `thunderbolt (no Qualcomm host router glue)`
- Nothing in the DT.
- Native coverage: **none** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| host router driver | TBD |
| PCIe/DP tunnel root complexes | TBD |
| large reverse-engineering effort | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Router register map and bring-up sequence | TBD | REA of `QcUsb4Bus8380.sys` |
| Q2 | Is there upstream work for Qualcomm USB4? | TBD | lore |

## 7. Acceptance

1. A USB4 dock enumerates PCIe and DP tunnels

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
