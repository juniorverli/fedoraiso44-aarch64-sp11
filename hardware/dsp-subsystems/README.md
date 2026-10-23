# dsp-subsystems

## 1. Summary

The audio DSP (ADSP) and compute DSP (CDSP) remote processors, and the IPC around them (GLINK, QRTR, protection-domain mapper). The ADSP also hosts battery management (pmic-glink: battery, charger, USB-C), audio and the sensor core, so it matters in phase 1 even though audio does not. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| ADSP | `ACPI\VEN_QCOM&DEV_0C1B&SUBSYS_MSHW0486&REV_000D` | Verified | `pnp-present.json` |
| CDSP | `ACPI\VEN_QCOM&DEV_0CB0&SUBSYS_CRD08380` | Verified | same |
| ADSP image | `surfacepro_ext_adsp8380.inf_arm64_3cc952aaca3564ae/qcadsp8380.mbn`, SHA-256 `921870a839ee2aba647b04598d62ed96f3d2d5dfbb2499fc842f9a6ff0e0da13` | Verified | `MANIFEST.sha256` |
| ADSP DT blob | Windows `adsp_dtbs.elf`; Linux asks `adsp_dtb.mbn` | Verified (both names) | DriverStore; `x1-microsoft-denali.dtsi` |
| CDSP image and DT blob | `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/qccdsp8380.mbn`, `cdsp_dtbs.elf` | Verified | `MANIFEST.sha256` |
| Service maps | `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`, `cdspr.jsn` | Verified (present) | DriverStore |

## 3. Windows

`qcsubsys8380` and `qcpil` load the images; `qcpdsr` is the protection-domain service registry; `qcipcrouter8380` is QRTR; `qcpmicglink8380` is the battery/charger/USB-C client; `qcadsprpc*` is FastRPC.

## 4. Linux 7.3

`remoteproc/qcom_q6v5_pas`, `rpmsg/qcom_glink_smem`, `net/qrtr`, `soc/qcom/pmic_glink` (+ `qcom_battmgr`, `pmic_glink_altmode`, `ucsi_glink`), `misc/fastrpc`. Userspace: `pd-mapper` (reads the `*.jsn` maps), `qrtr` tools. No modem, so no `rmtfs`/`tqftpserv` need is expected.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Windows to Linux firmware names | Firmware manifest (done in draft) |
| `*.jsn` consumer | Confirm `pd-mapper` in Fedora 44 and the path it reads (`/lib/firmware/qcom/x1e80100/microsoft/Denali/`?) |
| Is `adsp_dtbs.elf` byte-identical to what Linux expects as `adsp_dtb.mbn`? | Compare ELF headers with a known working X1E laptop firmware layout |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Does the ADSP boot and reach `running` with these images? | TBD | `/sys/class/remoteproc/*/state` on M2 |
| Q2 | Does `qcom_battmgr` report the battery alongside SSAM, and which one should GNOME use? | TBD | M2 `/sys/class/power_supply/` |

## 7. Acceptance

Both remoteprocs `running` after boot, `pd-mapper` serving, battery visible.

## 8. Requests

- firmware: resolve every entry with `component = "dsp-subsystems"`.
- image: install `pd-mapper` and `qrtr`; log `/sys/class/remoteproc/*/state` and `power_supply`.

## 9. Log

- 2026-10-23: dossier created from the static survey.
