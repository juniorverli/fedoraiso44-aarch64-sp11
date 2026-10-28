# dsp-subsystems test plan

Every device test reboots the operator's PC, so nothing here needs its own boot. Steps T1-T8 are read-only and are covered by the image collector plus the drop-in `hardware/dsp-subsystems/collector/dsp-subsystems.sh` (request R-I1; output file `extra-dsp-subsystems.txt`). Section 3 lists the few optional manual commands that write to sysfs; they never touch firmware, a charger or a battery limit (S3, S6) and are not needed for acceptance. Facts marked "M5" were already observed (`evidence/2026-10-28-m5-device-log.md`).

Boot arguments requested for the next ISO (R-I2), all diagnostic: `qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M`. The first two make the otherwise invisible `pr_debug` lines of the in-kernel mapper and the PDR client appear (`qcom_pd_mapper.c:194,200`, `pdr_interface.c:470`); the third records the GLINK open handshake that the CDSP edge fails (`drivers/rpmsg/qcom_glink_trace.h`, system `qcom_glink`; syntax from `Documentation/admin-guide/kernel-parameters.txt` `trace_event=:mod:<module>`).

## 1. Expected result, by step

| Step | Command (inside the drop-in or in `dmesg.txt`) | Expected | Meaning if different |
|:--|:--|:--|:--|
| T1 | `/sys/class/remoteproc/remoteproc*/{name,state,firmware}` | `adsp` `running` `qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn`; `cdsp` `running` `.../qccdsp8380.mbn` (M5: both) | `offline` plus a `Direct firmware load ... failed with error -2` line: firmware not reachable at probe (risk 1). `crashed`: see T6 |
| T2 | dmesg: `remoteproc remoteprocN: powering up`, `Booting fw image <path>, size <n>`, `remote processor <name> is now up` | sizes 22092168 (ADSP) and 3195304 (CDSP); `is now up` within 1 s of `Booting` for each | A gap of about 5 s before `adsp is now up`: the sysmon event to the CDSP timed out (seen in the GPU boot) |
| T3 | `qrtr-lookup` (package `qrtr`, installed in M5) | Local node 1: service 64 version 1 instance 1 (the in-kernel locator). ADSP node (expected 5, Inference): service 66 version 1 instance 74 (charger PD notifier) and the same for audio PD; service 43 (SSCTL) version 1 instance 20 (`0x14`). CDSP node: services 43 instance 23 (`0x17`) and 66 instance 76 if it answers | No row for a node: that edge's `IPCRTR` is not bound (M5 CDSP). No `64` row: pd-mapper not bound |
| T4 | `/sys/bus/auxiliary/devices/`: `qcom_common.pd-mapper.0` and `.1` with driver `qcom-pdm-mapper`; `pmic_glink.ucsi.0`, `pmic_glink.altmode.0`, `pmic_glink.power-supply.0` with drivers `pmic_glink_ucsi`, `pmic_glink_altmode`, `pmic_glink_power_supply` | all bound | An unbound `pd-mapper` device: module not loaded or `probe ... failed with error -97` (risk 2) |
| T4b | dmesg with `dyndbg`: `PDM: service 'tms/servreg' offset 0 returning N domains (of 5)`, `PDM: found msm/adsp/charger_pd / 74`; `PDR: Indication received from msm/adsp/charger_pd, state: 0x1fffffff` | the locator answered for `tms/servreg` with five domains; both charger and audio PD indications (M5 GPU boot: yes) | `PDR: service lookup for tms/servreg failed: -110` or `-6`: lookup dropped, no retry (risk 2) |
| T5 | `/sys/bus/rpmsg/devices/`: `*.IPCRTR.*` (driver `qcom_smd_qrtr`), `*.PMIC_RTR_ADSP_APPS.*` (driver `qcom_pmic_glink_rpmsg`), `*.adsp_apps.*` (`qcom,apr`), `*.fastrpcglink-apps-dsp.*` (`qcom,fastrpc`) on the ADSP edge `6800000.remoteproc:glink-edge`. CDSP edge `32300000.remoteproc:glink-edge`: `IPCRTR` and `fastrpcglink-apps-dsp` | ADSP: all four bound (M5). CDSP: bound only if H-C1/H-C2 resolve | An ADSP channel without driver: that module missing or failing |
| T6 | `/sys/class/power_supply/*` | `BAT1`, `ADP1` (SSAM); `qcom-battmgr-{bat,ac,usb,wls}`; `ucsi-source-psy-pmic_glink.ucsi.01` and `.02` (M5: all). With the charger plugged in a USB-C port: `qcom-battmgr-ac` or `-usb` `online: 1`, `status` Charging, `ucsi-source-psy-*` `online: 1` and `usb_type` showing PD | `qcom-battmgr-bat` attributes returning "No data available" or all zero: the PDR state is not `UP` |
| T7 | `/sys/class/typec/`, `/sys/class/usb_power_delivery/` | one `port0` and `port1` per connector once UCSI registered (for `usb-typec`) | none: UCSI client not registered |
| T8 | dmesg: no `crash detected`, `watchdog received`, `fatal error received`, `handling crash`, `recovering` | none (M5: none) | risk 3 |

## 2. Dmesg lines per failure (exact strings; source lines in v7.3)

| Risk | Line you would see | Source |
|:--|:--|:--|
| Firmware not reachable (ADSP) | `remoteproc remoteproc0: Direct firmware load for qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn failed with error -2` (twice), then `remoteproc remoteproc0: request_firmware failed: -2`; state stays `offline`, no retry | `firmware_loader/main.c:894-896`, `remoteproc_core.c:1973`, no retry: `:1698-1703` |
| DTB image missing | `qcom_q6v5_pas 6800000.remoteproc: Direct firmware load for qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn failed with error -2`, `qcom_q6v5_pas 6800000.remoteproc: request_firmware failed for qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn: -2` | `qcom_q6v5_pas.c:245-249` |
| Image rejected by TZ | `qcom_q6v5_pas 6800000.remoteproc: error -22 initializing firmware <path>` (value varies), `failed to authenticate image and release reset`, `failed to authenticate dtb image and release reset` | `mdt_loader.c:279-290`, `qcom_q6v5_pas.c:320,339` |
| Image loads but never reports ready | `qcom_q6v5_pas 6800000.remoteproc: start timed out`, then `remoteproc remoteproc0: can't start rproc adsp: -110` | `qcom_q6v5_pas.c:346`, `remoteproc_core.c:1290` |
| AOSS load state or interconnect | `qcom_q6v5_pas ...: failed to toggle load state`, `failed to set bandwidth request` | `qcom_q6v5.c:34,85` |
| pd-mapper cannot start | `PDM: no support for the platform, userspace daemon might be required.` (compatible not in the table); `PDM: error adding server <n>`; `qcom-pdm-mapper qcom_common.pd-mapper.0: probe with driver qcom-pdm-mapper failed with error -97` (no `qrtr`) | `qcom_pd_mapper.c:690,724`; driver core |
| PDR lookup fails (**not retried**, except `-ENXIO`) | `PDR: tms/servreg get domain list txn wait failed: -110` then `PDR: service lookup for tms/servreg failed: -110`; `PDR: msm/adsp/charger_pd register listener txn wait failed: -110` or `... register listener failed: 0x...` | `pdr_interface.c:378,445,143,149` |
| pmic_glink channel before its platform device | `qcom_pmic_glink_rpmsg ...PMIC_RTR_ADSP_APPS...: no pmic_glink device to attach to` | `pmic_glink.c:253` |
| Crash and recovery (SSR) | `qcom_q6v5_pas 6800000.remoteproc: watchdog received: <text>` or `watchdog without message` or `fatal error received: <text>`; `remoteproc remoteproc0: crash detected in adsp: type watchdog` (or `fatal error`); `remoteproc remoteproc0: handling crash #1 in adsp`; `remoteproc remoteproc0: recovering adsp`; `remoteproc remoteproc0: Minidump TOC not found in SMEM` (coredump step); then `Booting fw image ...` and `remote processor adsp is now up` | `qcom_q6v5.c:140-165`, `remoteproc_core.c:2761,1909,1863`, `qcom_common.c:167` |
| Windows "ignore watchdog" mattering (Hypothesis) | a `watchdog without message` shortly after boot, repeating after each recovery | `surfacepro_ext_adsp8380.inf:135` |
| Sysmon cross-notification | `qcom_q6v5_pas 32300000.remoteproc: timeout waiting for subsystem event response` (M5 GPU boot), `timeout waiting for ssctl service`, `timeout waiting for shutdown ack` | `qcom_sysmon.c:407,555,320` |
| GLINK edge cannot start | `failed to parse qcom,remote-pid`, `failed to allocate glink descriptors`, `failed to request IRQ`, then `remoteproc remoteprocN: failed to probe subdevices for adsp: <err>` | `qcom_glink_smem.c:260-327`, `remoteproc_core.c:1303` |
| Channel never acknowledged (M5, CDSP) | `qcom_smd_qrtr 32300000.remoteproc:glink-edge.IPCRTR.-1.-1: failed to create endpoint` then `probe with driver qcom_smd_qrtr failed with error -12`; `qcom,fastrpc ...: failed to create endpoint` then `error -12` | `rpmsg_core.c:456`, `qcom_glink_native.c:1288-1316` |
| Audio framework not ready (M5) | `qcom-apm gprsvc:service:2:1: CMD timeout for [1001021] opcode` | `audioreach.c:623` |

## 3. Optional manual steps (operator or a worker with a shell on the device; root)

All are driver-level (no firmware, no charger, no limit). Skip any that is inconvenient; none gates acceptance.

1. CDSP race test (H-C2): after the system has been up for several minutes, `ls /sys/bus/rpmsg/devices | grep 32300000`, then for `IPCRTR`: `echo 32300000.remoteproc:glink-edge.IPCRTR.-1.-1 > /sys/bus/rpmsg/drivers/qcom_smd_qrtr/bind` and read `dmesg | tail`. A success means a timing race; a timeout again means the CDSP does not answer (H-C1).
2. PD-charger log (optional, ADSP charger firmware log through a debug module): `modprobe qcom_pmic_pdcharger_ulog; echo 1 > /sys/kernel/tracing/events/pmic_pdcharger_ulog/pmic_pdcharger_ulog_msg/enable; sleep 30; cat /sys/kernel/tracing/trace`. The module requests a log from the ADSP once a second (read request, `pmic_pdcharger_ulog.c:20-60`); remove it with `modprobe -r qcom_pmic_pdcharger_ulog` afterwards. Use it with a charger plugged in, when `usb-typec` or `ec-sam` need charger-side evidence.
3. SSR on the CDSP only (exercises recovery without touching the ADSP, which carries USB-C and the battery): `echo 1 > /sys/kernel/debug/remoteproc/remoteproc1/crash` (check `name` is `cdsp` first). Expected lines: the "Crash and recovery" row. **Never write `crash` for the ADSP** while the system root is on a USB-C stick.

## 4. Acceptance (from the dossier)

1. T1 and T2 pass for the ADSP on every boot entry that ships (M5: pass).
2. T3 and T4 show the in-kernel mapper serving `tms/servreg` and the ADSP charger PD notifier (M5: PDR indications seen; `qrtr-lookup` pending).
3. T6: `qcom-battmgr-*` and `ucsi-source-psy-*` present and updating with a charger plugged and unplugged (M5: present, plug test pending).
4. The CDSP requirement (`running` plus T5 CDSP rows) is not on the usable-tablet path; track it for the `npu` worker.
