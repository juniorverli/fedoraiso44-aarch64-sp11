# dsp-subsystems

## 1. Summary

The audio DSP (ADSP) and compute DSP (CDSP) remote processors, and the IPC around them (GLINK, QRTR, in-kernel protection-domain mapper). The ADSP hosts pmic-glink (battery manager, UCSI, altmode), so battery, charging and USB-C depend on it. Status: `testing`. On the M5 ISO both processors are `running`, PDR is up for the charger and audio PDs, and `qcom-battmgr-*` and `ucsi-source-psy-*` exist and report; the CDSP does not acknowledge GLINK channels that Linux opens (section 6, Q3), which does not touch the usable-tablet set. No patch is needed.

Evidence files: `evidence/2026-10-28-pas-path-static.md` (path map with `file:line`), `evidence/2026-10-28-blob-headers.md` (blob names and ELF headers), `evidence/2026-10-28-m5-device-log.md` (M5 device log). Plan: `test-plan.md`. Collector drop-in: `collector/dsp-subsystems.sh`. Header tool: `tools/mdtcheck.py`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| ADSP | `ACPI\VEN_QCOM&DEV_0C1B&SUBSYS_MSHW0486&REV_000D`; Linux `qcom,x1e80100-adsp-pas` at `0x06800000`, pas_id 1, DTB pas_id `0x24`, UEFI "lite" ids `0x1f`/`0x29` | Verified | `pnp-present.json`; `hamoa.dtsi:4274`; `qcom_q6v5_pas.c:1244-1263` |
| CDSP | `ACPI\VEN_QCOM&DEV_0CB0&SUBSYS_CRD08380`; Linux `qcom,x1e80100-cdsp-pas` at `0x32300000`, pas_id 18, DTB pas_id `0x25` | Verified | `pnp-present.json`; `hamoa.dtsi:8944`; `qcom_q6v5_pas.c:1265-1283` |
| ADSP memory | image `0x87e00000` +`0x3a00000`; DTB `0x8b800000` +`0x80000` | Verified | `hamoa.dtsi:578-586` |
| CDSP memory | image `0x8b900000` +`0x2000000`; DTB `0x8d900000` +`0x80000` | Verified | `hamoa.dtsi:588-596` |
| GLINK edges | ADSP `label = "lpass"`, remote-pid 2; CDSP `label = "cdsp"`, remote-pid 5; SMP2P entries `master-kernel`/`slave-kernel` | Verified | `hamoa.dtsi:699-751,4310-4318,8982-8990` |
| Images (staged, in the initramfs) | `qcadsp8380.mbn` `921870a8...0da13`; `adsp_dtbs.elf` as `adsp_dtb.mbn` `544bd795...6ff4`; `qccdsp8380.mbn` `4a67a033...c789`; `cdsp_dtbs.elf` as `cdsp_dtb.mbn` `93941f04...797f`. Spans equal the DT regions | Verified | `firmware/manifest.toml`; `evidence/2026-10-28-blob-headers.md` |
| Protection domains (in-kernel) | `msm/adsp/{audio_pd,root_pd,charger_pd,sensor_pd}` instance 74, `msm/cdsp/root_pd` 76, plus `tms/servreg` on each; equal to the five Windows `*.jsn` | Verified | `qcom_pd_mapper.c:609-616,253-312`; `adspr.jsn`, `adsps.jsn`, `adspua.jsn`, `battmgr.jsn`, `cdspr.jsn` |
| Battery gauge seen by Linux | `BAT1` (SSAM) and `qcom-battmgr-bat` (ADSP) report the same cell (`energy_full` 44780000, `voltage_now` 7323000) | Verified | `power_supply.txt` of boot `3f0e2cc1` |
| Charge limit location | ADSP firmware or Surface firmware; the DT has no `charge_limit_*` nvmem cells | TBD | `qcom_battmgr.c:731-751` |

## 3. Windows

| Package (`DriverStore`) | What it does |
|:--|:--|
| `surfacepro_ext_adsp8380` | ADSP image `qcadsp8380.mbn`, DTB `adsp_dtbs.elf`, resource bin `RADS.bin`, the PD maps `adspr/adsps/adspua/battmgr.jsn`, ADSP user libraries. Registry: DTB supported, UEFI-loaded "lite" image with TZ ids `0x1F`/`0x29` ("Need Restart"), `IgnoreWdogEnabled = 1`, reservations `0x3A00000` (ADSP) and `0x11000` (DTB); three PDs (audio, charger, sensor) mapped to the ADSP |
| `qcnspmcdm_ext_cdsp8380` | CDSP image `qccdsp8380.mbn`, DTB `cdsp_dtbs.elf`, `cdspr.jsn`, CDSP user libraries; reservation `0x2000000` |
| `qcsubsys8380`, `qcpil*`, `qcsubsys_ext_*` | subsystem and PIL loader framework |
| `qcpdsr` | protection-domain service registry (the Windows counterpart of the in-kernel mapper) |
| `qcipcrouter8380`, `qcglink8380` | QRTR and GLINK |
| `qcpmicglink8380` (`ACPI\QCOM0C8E`) | PMIC GLink transport |
| `qcusbcucsi8380` (`ACPI\USBC000`, "UCM-UCSI ACPI Device") | UCSI over PMIC GLink |
| `surfacebattery` | SSAM battery; the only battery-class device in the live inventory |
| `qcadsprpc*` | FastRPC |

Verified from `live-inventory/pnp-present.json` and the INFs (`evidence/2026-10-28-pas-path-static.md` section 5).

## 4. Linux 7.3

### 4.1 Drivers and DT

`remoteproc/qcom_q6v5_pas`, `rpmsg/qcom_glink_smem`, `net/qrtr` (name service in the kernel, `qrtr_smd` for the `IPCRTR` channel), `soc/qcom/qcom_pd_mapper` (in-kernel; Fedora 44 has no userspace `pd-mapper`), `soc/qcom/pdr_interface`, `soc/qcom/pmic_glink` with `qcom_battmgr`, `ucsi_glink`, `pmic_glink_altmode`, `misc/fastrpc`. DT: `x1-microsoft-denali.dtsi:1038-1050` (firmware names), `:35-123` (pmic-glink), `hamoa.dtsi` for the nodes. The full path from PAS probe to services is in `evidence/2026-10-28-pas-path-static.md`; the summary:

1. PAS probe reads the two `firmware-name` strings (`qcom_q6v5_pas.c:838-850`); there is no `qcom,dtb-firmware-name` in 7.3.
2. `auto_boot` starts `request_firmware_nowait()` once, with no retry (`remoteproc_core.c:1698-1703`); `rproc_boot()` loads the image again and calls `rproc_start()`.
3. `rproc_start()` loads the DTB image, prepares subdevices (**the pd-mapper auxiliary device is created here, before the DSP runs**), starts the DSP (TZ authenticates DTB then image, 5 s for `ready`), then starts the GLINK edge.
4. The ADSP opens `IPCRTR`, `PMIC_RTR_ADSP_APPS`, `fastrpcglink-apps-dsp`, `adsp_apps`; `qrtr_smd` bridges `IPCRTR` into QRTR, where the ADSP's servreg notifier (service 66, instance 74) appears.
5. `pmic_glink` (platform device, probed independently of the ADSP) holds the PDR lookup for `tms/servreg` / `msm/adsp/charger_pd`; when the PD is `UP` and the `PMIC_RTR_ADSP_APPS` endpoint exists, battmgr, UCSI and altmode are told `UP`.

### 4.2 What each function needs (Verified)

Battery, charging and USB-C each need: the ADSP `running`; `qrtr` and `qrtr_smd` for the ADSP edge; the mapper answering `tms/servreg` with `msm/adsp/charger_pd`; the `PMIC_RTR_ADSP_APPS` channel; the ADSP's charger PD. USB-C also needs the connector DT, `ps883x` retimers and DWC3 (`usb-typec`). Nothing needs the CDSP. Table in the static evidence, section 4.

### 4.3 What can go wrong, and the line that shows it

Exact strings and sources are in `test-plan.md` section 2. Summary, with the grade of each risk:

| Risk | Effect | Line (short) | Seen in M5 | Grade |
|:--|:--|:--|:--|:--|
| ADSP boots before the firmware is reachable | The driver asks once; a missing file leaves the DSP `offline` until someone writes `start` to sysfs | `Direct firmware load for .../qcadsp8380.mbn failed with error -2`, `remoteproc remoteproc0: request_firmware failed: -2` | no (blobs are in the initramfs, sizes in `Booting fw image` match) | Verified mechanism |
| pd-mapper or PDR ordering | The mapper starts before the DSP (subdevice prepare), so the order is safe if `qrtr` and `qcom_pd_mapper` are loadable. A PDR lookup that fails with anything except `-ENXIO` is deleted and never retried, so pmic-glink would stay `DOWN` | `PDR: service lookup for tms/servreg failed: -110`; `qcom-pdm-mapper ... probe ... failed with error -97` | no | Verified mechanism, Inference for the likelihood |
| SSR and crash recovery | ADSP crash drops GLINK, so `pmic_glink`, battmgr, UCSI go `DOWN` and USB-C control is lost until recovery completes (a USB-C root stick may disappear). Recovery reloads both images from `/lib/firmware` of the real root, which has them (image L0 6.3 and the install listing) | `crash detected in adsp: type watchdog`, `handling crash #1`, `recovering adsp`, `Minidump TOC not found in SMEM` | no | Verified mechanism |
| Windows ignores ADSP watchdog bites (`IgnoreWdogEnabled = 1`) | If Linux sees a bite that Windows ignores, recovery would loop | `watchdog without message` repeating | no | Hypothesis; killed by a clean T8 on every boot |
| `remoteproc` auto-boot | Both processors start at probe, even when GLINK consumers are missing; with `qcom_q6v5_pas` blacklisted nothing starts them | `powering up adsp` | yes, as designed | Verified |
| CDSP failing | None of battery, charging, USB-C. Costs: 5 s stalls in `qrtr_smd` and `fastrpc` module loads, a 5 s late `adsp is now up` (sysmon event to the CDSP), no `/dev/fastrpc-cdsp*` | see section 6 Q3 | yes | Verified for the effects |
| UEFI-loaded ADSP "lite" image still running | `qcom_pas_load()` shuts down ids `0x1f` and `0x29` first; an error is ignored | none on success | no line | Verified in code, Inference that it was needed |

### 4.4 Should D20's early PAS stay? Advice: keep for now, revisit for the installed system (grade: Inference)

- For: the M5 boot reached GNOME and every DSP firmware file was readable at probe; `request_firmware_nowait()` has no retry, so any ordering mistake in the initramfs leaves the ADSP off until a manual `start`; the early start costs nothing visible (no `Direct firmware load` lines, no crash lines, T1 and T2 pass); recovery after switch-root works because the same four files are in the root file system.
- Against: the early start puts pmic-glink (UCSI, altmode) and the ADSP audio stack into the initramfs phase, and D20 bundled four changes at once, so no log isolates the PAS from `leds_qcom_lpg`, `clk_ignore_unused` or the parity DTB. M5 removed the "no early DSP" comparison entry.
- Advice: keep the early PAS in the live ISO (do not change what works while the order of D22 items is open). When a build happens anyway, bring back one entry with `rd.driver.blacklist=qcom_q6v5_pas` (request R-I3) so the next device batch can settle whether the early start is needed. For the installed system (NVMe root, mounted in about two seconds) the Fedora-native choice is late loading: no firmware in the initramfs, module loaded by udev after switch-root. Decide after the entry comparison; do not decide on Inference alone.

### 4.5 Patches

None needed or written. Candidates considered and why none: the battmgr thresholds (S6) are a policy question for the orchestrator (request O1), not a driver fault; `qcom_pas_load()` does not release the DTB firmware on success (`qcom_q6v5_pas.c:245-256`, 73 KiB and 40 KiB once per start; harmless, upstream's to fix); the CDSP edge has no kernel-side fault found.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Windows to Linux firmware names | Closed: four entries confirmed (`evidence/2026-10-28-blob-headers.md`) |
| `*.jsn` consumer | Closed: no userspace mapper; the in-kernel mapper has the same domains; PDR indications seen on the device |
| `adsp_dtbs.elf` content versus the name | Closed for format and placement; the ADSP reaches `running` and `pmic_glink` binds, so the content is accepted by TZ and the ADSP |
| CDSP does not acknowledge GLINK channels | Diagnostics requested (R-I2, R-I1); decision after the next boot (Q3) |
| Two batteries | `ec-sam` decides which supply the desktop uses (request E1) |
| S6 charge thresholds writable | Orchestrator decision (request O1) |
| Observability of the mapper and PDR | Dynamic debug in the next ISO (R-I2) |
| ADSP audio framework not ready | Audio workers; S1 unaffected (no card) |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Does the ADSP boot and reach `running` with these images? | **Verified: yes** (M5 `remoteproc.txt`, `remote processor adsp is now up`, boots `3f0e2cc1` and `0ee2fa1a`) | answered |
| Q2 | Does `qcom_battmgr` report the battery alongside SSAM? | **Verified: both register and agree**; which one the desktop should use is Inference (keep `BAT1`) | request E1 |
| Q3 | Why does the CDSP not acknowledge channels Linux opens (`failed to create endpoint`, -12 = a 5 s GLINK open-ack timeout)? | TBD; H-C1 CDSP never services APPS channels, H-C2 start-up race, H-C3 IPCC/power collapse (details in the device-log evidence) | GLINK trace, `qrtr-lookup`, `qcom_stats/cdsp`, rebind test (test plan 3.1) |
| Q4 | Which QRTR node is the ADSP and which the CDSP? | Inference: ADSP is node 5 (only registered endpoint when `failed while handling packet from 5:-2` appeared) | `qrtr-lookup` |
| Q5 | Does any DSP service need `tms/pdr_enabled`? | **Verified: no** for charger and audio PDs (PDR indications seen with `x1e80100_domains`, which lacks it) | answered |
| Q6 | Where is the Windows charge limit stored (ADSP, UEFI, EC)? | TBD | `ec-sam` and `power-thermal` reading the SSAM/UEFI settings; not by writing |
| Q7 | Does the early PAS matter for booting from a USB-C stick? | Hypothesis | the "no early DSP" entry (R-I3) |
| Q8 | Does the ADSP SPF audio framework become ready later? | TBD | `qcom-apm` lines over time in the next boot; audio workers |

## 7. Acceptance

Both remoteprocs `running` after boot, PDR for the charger PD up, `qcom-battmgr-*` and UCSI supplies present and tracking a charger plugged and unplugged. Status of each: ADSP running (M5), PDR up (M5), supplies present (M5), plug test pending. The CDSP is tracked separately for the `npu` worker. `pass` is the orchestrator's call.

## 8. Requests

- **image** (R-I1): install `collector/dsp-subsystems.sh` as `/etc/sp11-log-collector.d/dsp-subsystems.sh` (the collector extension point, `image/README.md`); it is read-only and timeouts are inside.
- **image** (R-I2): add to the default entry: `qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M` (diagnostic only; syntax in `Documentation/admin-guide/dynamic-debug-howto.rst:249-269` and `kernel-parameters.txt` `trace_event`).
- **image** (R-I3): when the next ISO is built anyway, restore the entry `SP11 debug, no early DSP` (`rd.driver.blacklist=qcom_q6v5_pas`, `sp11.entry=nodsp`).
- **image** (R-I4): no unit, udev rule or script may write `charge_control_start_threshold` or `charge_control_end_threshold` (S6). `rmtfs` is installed in the M5 image; the drop-in lists its state, no action yet.
- **ec-sam** (E1): `BAT1` (SSAM) and `qcom-battmgr-bat` (ADSP) both register and report the same cell. Windows shows only the SSAM battery. Recommendation: keep `BAT1` as the desktop battery and have the image hide `qcom-battmgr-bat` from UPower (a udev property such as `UPOWER_IGNORE_DEVICE=1` on that supply), but keep `qcom-battmgr-ac`, `-usb` and the `ucsi-source-psy-*` supplies for AC/USB state. Confirm with the charger-plugged log of T6.
- **usb-typec** (U1): the ADSP side is not blocking you: UCSI registered both ports (`ucsi-source-psy-pmic_glink.ucsi.01` and `.02`), PDR is up, `pmic_glink_altmode` and `ps883x` are loaded. The `Failed to create device link ... pmic-glink ... connector@N` lines are fw_devlink notices for the connector graph.
- **firmware**: no correction. Optional: add `RADS.bin` (SHA-256 `ff4af19d6973cf87399392255722c56c75efd216add4d7ac718a3e8a193dfa09`, 1401 bytes, Windows resource bin) and the ADSP/CDSP user-space libraries to `[[not_shipped]]` with the reason "no kernel request; user-space FastRPC only".
- **kernel**: none. `CONFIG_QCOM_PMIC_PDCHARGER_ULOG=m`, `QCOM_Q6V5_PAS=m`, `QCOM_PD_MAPPER=m`, `QRTR=m`, `QRTR_SMD=m`, `FASTRPC` (`QCOM_FASTRPC=m`) are already set and stay.
- **orchestrator** (O1): S6: `qcom-battmgr-bat` exposes writable charge thresholds that the driver cannot compare with the firmware's own limit (`qcom_battmgr.c:662-724,731-751,760-792`). Decide whether to enforce read-only (a small local patch for the X1E variant) or rely on R-I4 plus no UI toggle. (O2) The M5 collector's DP debugfs read oopses `msm_dp_test_active_show` (`dmesg.txt` `18:16:57,186346`); this belongs to display-lcd.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-28: path map from PAS probe to services with `file:line`; blob names, hashes and ELF program headers confirmed independently; risk list and the D20 advice; M5 device logs read: both DSPs `running`, PDR and pmic-glink supplies work, CDSP GLINK edge fails with a 5 s open-ack timeout (-12), two batteries, S6 note; collector drop-in, test plan, requests. Status `testing`. No patch.
