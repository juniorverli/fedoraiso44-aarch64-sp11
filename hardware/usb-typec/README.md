# usb-typec

## 1. Summary

Two USB-C ports with DWC3 controllers, PS8830 retimers, pmic-glink UCSI for role and orientation, DisplayPort Alt Mode and charging. Linux 7.3 describes both ports. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C8B` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C8C` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0D08 (multiport xHCI)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CA4 (Type-C)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_USB&DEV_C000 (UCSI)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `UEFI\RES_{05575d61-...} / {59b50971-...} (retimers)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcusbcucsi8380` | TBD |
| `surfaceucmucsihidclient` | TBD |
| `qcxhcifilter8380` | TBD |
| `qcusbfnssfilter8380` | TBD |
| `surfaceretimer0` | TBD |
| `surfaceretimer1` | TBD |
| `surfaceude` | TBD |

## 4. Linux 7.3

- Driver: `usb/dwc3/dwc3-qcom`
- Driver: `phy-qcom-qmp-combo`
- Driver: `phy-qcom-eusb2 + smb2360 repeater`
- Driver: `typec/mux/ps883x`
- Driver: `soc/qcom/pmic_glink_altmode`
- Driver: `typec/ucsi/ucsi_glink`
- Driver: `drm/msm/dp (DP0/DP1)`
- DT: `x1-microsoft-denali.dtsi pmic-glink connectors, &i2c3/&i2c7 typec-mux@8, &usb_1_ss0/1, &mdss_dp0/1`
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| retimer 1 reset line has no pinctrl state | TBD |
| multiport controller QCOM0D08 purpose on this chassis | TBD |
| dr_mode host only (no gadget) | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Retimer 1 reset pin state and supplies | TBD | DSDT; `qcusbcucsi8380` REA |
| Q2 | What is the `QCOM0D08` multiport xHCI connected to? | TBD | DSDT `_UPC`/`_PLD` |
| Q3 | Is device (gadget) mode wanted? | TBD | Operator |

## 7. Acceptance

1. USB 3 storage at 5/10 Gbit/s on both ports, both orientations
2. External monitor over DP Alt Mode
3. Charging from a USB-C PD charger

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
