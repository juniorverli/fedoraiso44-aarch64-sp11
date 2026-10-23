# storage

## 1. Summary

The WD SN740 NVMe SSD on PCIe6a. Linux 7.3 supports it natively; the open point is installing next to Windows safely. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `PCI\VEN_15B7&DEV_5015&SUBSYS_501515B7` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `stornvme (inbox)` | TBD |
| `surfacestoragefwupdate* (firmware update only)` | TBD |

## 4. Linux 7.3

- Driver: `pci/controller/dwc/pcie-qcom`
- Driver: `phy-qcom-qmp-pcie`
- Driver: `nvme`
- DT: `x1-microsoft-denali.dtsi &pcie6a, &pcie6a_phy, &pcie6a_port0`
- Native coverage: **full** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| install target alongside Windows: partition plan and BitLocker (risk S4) | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Partition layout and free space for a dual boot | TBD | Read-only `lsblk`/`sfdisk -d` on the live ISO |
| Q2 | BitLocker state of the Windows partition | TBD | Operator, before any install (risk S4) |

## 7. Acceptance

1. Live ISO sees the disk; install to free space keeps Windows bootable

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
