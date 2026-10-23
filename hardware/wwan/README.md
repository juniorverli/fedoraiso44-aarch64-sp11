# wwan

## 1. Summary

The 5G modem and GNSS of the cellular SKU. This unit is the Wi-Fi-only LCD SKU: no modem, MHI or GNSS device is present in the Windows inventory, and the TCON capsule is the Wi-Fi LCD variant. The driver packages exist because the image is shared across SKUs. Status: `absent`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | none present | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcwwanpowerdown` | TBD |
| `surface_mbbnetadapter` | TBD |
| `surface_mbbfwupdatedriver` | TBD |
| `surface_mhihost` | TBD |
| `surface_qmuxmdm` | TBD |
| `surface_gnss` | TBD |
| `surface_5gnrcoexmgr` | TBD |
| `surface_5gnrcoexmgr_ext` | TBD |
| `surface_thermalmdm` | TBD |
| `hidtelephonydriver` | TBD |

## 4. Linux 7.3

- Nothing in the DT.
- Native coverage: **n/a** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| none | — |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Confirm absence on Linux | TBD | `lspci` shows no `17cb:0308` |

## 7. Acceptance

1. Not applicable

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
