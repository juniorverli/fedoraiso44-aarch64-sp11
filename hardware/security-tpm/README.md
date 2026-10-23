# security-tpm

## 1. Summary

The TPM 2.0 implemented by Pluton/TrEE as a QSEE application, plus secure apps and UEFI variables. Linux 7.3 has QSEECOM and UEFI variable access for this machine, but no TPM driver over QSEE. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `Root\PlutonQc` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `{1F75CF6D-...}\TrEETPM` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CE4 (secapp)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0C87 / 0C8D (secure processor)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CAC (secure kernel ext)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `plutonqc` | TBD |
| `qctree` | TBD |
| `qctree_i` | TBD |
| `qctreeextqcom8380` | TBD |
| `qcsecapp` | TBD |
| `qcscm` | TBD |
| `qcskext8380` | TBD |
| `qcssgservicesumd` | TBD |
| `qcconnectionsecurity8380` | TBD |
| `qcrpen` | TBD |
| `qcsocpartition` | TBD |
| `surface_uefi_stpm` | TBD |

## 4. Linux 7.3

- Driver: `firmware/qcom/qcom_scm`
- Driver: `qcom_qseecom`
- Driver: `qcom_qseecom_uefisecapp (microsoft,denali allowlisted)`
- Nothing in the DT.
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no TPM driver over the QSEE TPM app | TBD |
| TPM2 ACPI table start method not supported by tpm_crb | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | TPM command transport to the TrEE app | TBD | REA of `QcTrEE.sys`, `qcsecapp.sys` |
| Q2 | Is there upstream work on a QSEE TPM driver? | TBD | lore |

## 7. Acceptance

1. `tpm2_getcap properties-fixed` works; measured boot PCRs readable

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
