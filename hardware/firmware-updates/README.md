# firmware-updates

## 1. Summary

Firmware of the UEFI, EC, TCON, retimers, touch, Type Cover, pen, SSD and docks. Out of scope until the operator asks. Any update uses only vendor-signed images through the vendor path (risk S3). Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `UEFI\RES_{4a5d1268-...} (UEFI)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{632cbe1c-...} (SAM)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{82e97d6d-...} (TCON)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{81a1a6b3-...} (SMF)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{1da748b0-...} (DPP)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `HID MSHW0484 Col06/Col08 (touch/pen)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `HID Target_KIP Col02 (Type Cover)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `surface_uefi` | TBD |
| `surface_uefi_stpm` | TBD |
| `surfacenullcapsule` | TBD |
| `surfacetconwifionlylcd` | TBD |
| `surfaceretimer0` | TBD |
| `surfaceretimer1` | TBD |
| `surface.smf.117.0.*` | TBD |
| `surfacetouchg6fwupdateextnpackage*` | TBD |
| `surfacetypecoverv7fwupdate` | TBD |
| `surfacepen0c0ffirmwareupdate` | TBD |
| `surfacestoragefwupdate*` | TBD |
| `hidcfu (inbox)` | TBD |

## 4. Linux 7.3

- Driver: `efi capsule loader / fwupd (UEFI ESRT)`
- Nothing in the DT.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| out of scope until the operator asks (risk S3) | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which updates fwupd can apply through the UEFI ESRT capsule path? | TBD | `fwupdmgr get-devices` on the device |

## 7. Acceptance

1. Not applicable until scheduled

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
