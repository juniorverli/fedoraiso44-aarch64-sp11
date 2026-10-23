# npu

## 1. Summary

The Hexagon NPU (HTP v73) inside the CDSP, shown by Windows as a compute accelerator. Linux has FastRPC to the CDSP but no open accelerator driver; any workload would need Qualcomm's userspace runtime. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0D0A&REV_008A (ComputeAccelerator)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CC3 (NSP0 CDSP SW thermal)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Windows device | `ACPI\VEN_QCOM&DEV_0CF8 (NSP limits)` | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Hexagon generation | HTP **V73** | Verified (file names) | `qcnspmcdm8380.inf_arm64_*/HTP/libQnnHtpV73SkelDrv.so`, `QnnHtpV73StubDrv.dll` |
| Windows driver versions | `30.0.0220.3000` (2026-01-08, folder `..._553f7b0d71497f2c`) and `30.0.0219.1000` (2025-11-09, folder `..._e663a92a933cab52`); active one TBD | Verified (INF `DriverVer`) | `qcnspmcdm8380.inf` in each folder |
| INF binding | `qcnspmcdm8380` binds `ACPI\VEN_QCOM&DEV_0D0A`; `qcnspmcdm_ext_cdsp8380` extends `QCOM0D0A` and the CDSP `QCOM0CB0` | Verified | same INFs |
| CDSP-side payload | `fastrpc_shell_3`, `fastrpc_shell_unsigned_3`, `libsysmon*_skel.so`, `libQ6MSFR_manager_skel*.so`, `libbenchmark_skel.so`, `example_image*.so`, `map_SHARED_LIBS_hamoa.cdsp.prodQ.txt` (Hexagon binaries, not Windows code) | Verified (present) | `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/CDSP/` |
| Linux FastRPC on CDSP | `fastrpc` node (`label = "cdsp"`, channel `fastrpcglink-apps-dsp`) with `qcom,fastrpc-compute-cb` context banks, SMMU stream IDs `0x0c01`, `0x0c02`, ... | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi` (inside `remoteproc_cdsp`) |
| Linux accel driver for this NPU | none: `drivers/accel/` has `qaic` (Cloud AI 100 PCIe card, a different product), `ivpu`, `amdxdna`, `habanalabs`, `ethosu`, `rocket` | Verified | `sources/linux/drivers/accel/` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcnspmcdm8380` | TBD |
| `qcnspmcdm_ext_cdsp8380` | TBD |
| `qcadsprpc8380` | TBD |
| `surfacemachinelearningservicenulldriver` | TBD |

## 4. Linux 7.3

- Driver: `misc/fastrpc (cdsp)`
- Driver: `remoteproc/qcom_q6v5_pas (cdsp)`
- Driver: `userspace: fastrpc library; QNN/HTP runtime is proprietary`
- DT: `hamoa.dtsi remoteproc_cdsp fastrpc node`
- Native coverage: **partial** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| no open accel driver for the Hexagon NPU | TBD |
| runtime and skel libraries are Windows/QNN binaries | TBD |
| useful workload path on Linux undefined | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Can the open FastRPC userspace run a test skel on the CDSP? | TBD | Fedora `fastrpc` package and a sample |
| Q2 | Is there a licensed Linux QNN/HTP runtime usable here? | TBD | Qualcomm AI Engine Direct SDK terms |
| Q3 | Thermal limits for the NSP | TBD | `QCOM0CF8`, `QCOM0CC3` policies (power-thermal) |
| Q4 | Can the open Linux FastRPC userspace load the CDSP shell and a skel shipped in `qcnspmcdm_ext_cdsp8380` (signed vs unsigned PD)? | TBD | `fastrpc` userspace source (search path, `fastrpc_shell_3`), a test on the device |
| Q5 | Which `qcnspmcdm8380` version is active, and does the HTP skel version have to match a Linux QNN runtime version? | TBD | sources worker active-package table; QNN SDK release notes |
| Q6 | Is any upstream or posted kernel work for a Qualcomm Hexagon NPU accel interface (beyond FastRPC)? | TBD | lore linux-arm-msm / dri-devel search |

## 7. Acceptance

1. A FastRPC test call to the CDSP returns successfully

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: HTP V73, Windows package contents and versions, CDSP FastRPC DT node, absence of an accel driver verified.
