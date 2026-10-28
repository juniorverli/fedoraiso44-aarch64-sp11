# Path from PAS probe to working services (Linux v7.3, static)

Every `file:line` is in `sources/linux` (tag `v7.3`, `c03c1a14507dfaf8b856c2608f9ac216021fc222`). Config facts come from the M5 kernel `.config` (`out/build/kernel/rpmbuild/BUILD/kernel-7.3.0-build/kernel-7.3/linux-7.3.0-65.sp11.3.fc44.aarch64/.config`). Grades follow `agents/protocol.md` section 5. Device facts from the M5 log are in `2026-10-28-m5-device-log.md`.

## 1. DT nodes (Verified)

| Item | Where | Value |
|:--|:--|:--|
| Enable ADSP, firmware names | `arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1038-1043` | `firmware-name = "qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn", "qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn"`; `status = "okay"` |
| Enable CDSP, firmware names | `x1-microsoft-denali.dtsi:1045-1050` | `qccdsp8380.mbn`, `cdsp_dtb.mbn`; `status = "okay"` |
| ADSP node | `hamoa.dtsi:4274-4309` | compatible `qcom,x1e80100-adsp-pas`; five IRQs wdog, fatal, ready, handover, stop-ack (`:4278-4289`); clock `xo`; power domains `lcx`, `lmx` (`:4291-4295`); interconnect `lpass_lpicx_noc` to `mc_virt` (`:4297`); `memory-region = <&adspslpi_mem>, <&q6_adsp_dtb_mem>` (`:4300-4301`); `qcom,qmp = <&aoss_qmp>`; `qcom,smem-states = <&smp2p_adsp_out 0>`, name `stop` (`:4305-4306`) |
| ADSP memory | `hamoa.dtsi:578-586` | `adspslpi_mem` `0x87e00000` size `0x3a00000`; `q6_adsp_dtb_mem` `0x8b800000` size `0x80000` |
| ADSP GLINK edge | `hamoa.dtsi:4310-4318` | label `lpass`, `qcom,remote-pid = <2>`, mbox `IPCC_CLIENT_LPASS` / `IPCC_MPROC_SIGNAL_GLINK_QMP` |
| ADSP fastrpc | `hamoa.dtsi:4320-4371` | `label = "adsp"`, channel `fastrpcglink-apps-dsp`, `memory-region = <&adsp_rpc_remote_heap_mem>` (`:548`), compute-cb 3..7 |
| ADSP GPR (audio) | `hamoa.dtsi:4372-4420` | channel `adsp_apps`, `q6apm`, `q6prm`, both with `qcom,protection-domain = "avs/audio", "msm/adsp/audio_pd"` |
| CDSP node | `hamoa.dtsi:8944-9110` | `qcom,x1e80100-cdsp-pas`; power domains `cx`, `mxc`, `nsp`; `memory-region = <&cdsp_mem>, <&q6_cdsp_dtb_mem>` (`cdsp_mem` `0x8b900000` size `0x2000000`, `q6_cdsp_dtb_mem` `0x8d900000` size `0x80000`, `hamoa.dtsi:588-596`); `qcom,smem-states = <&smp2p_cdsp_out 0>`; GLINK edge label `cdsp`, `qcom,remote-pid = <5>`; fastrpc `label = "cdsp"` |
| SMP2P | `hamoa.dtsi:699-751` | `smp2p-adsp` (smem 443/429, remote-pid 2), `smp2p-cdsp` (smem 94/432, remote-pid 5), entries `master-kernel` (out) and `slave-kernel` (in) |
| pmic-glink | `x1-microsoft-denali.dtsi:35-123` | root-level node (not under a `glink-edge`), compatible `qcom,x1e80100-pmic-glink`, `qcom,sm8550-pmic-glink`, `qcom,pmic-glink`; `orientation-gpios` tlmm 121 and 123; `connector@0` and `connector@1`, each with ports 0 (DWC3 HS), 1 (retimer SS), 2 (retimer SBU) |
| Binding | `Documentation/devicetree/bindings/remoteproc/qcom,sm8550-pas.yaml:68-71` | `firmware-name` has two items: Hexagon image, Hexagon DT image. **There is no `qcom,dtb-firmware-name` property in v7.3** (grep over `drivers`, `Documentation`, `arch/arm64/boot/dts/qcom` finds none) |
| DT check | `out/rpms/kernel-7.3.0-65.sp11.3.fc44.aarch64.dtbs-check.log` | 26 lines, none names remoteproc, pmic-glink, adsp, cdsp, fastrpc or glink |

## 2. Driver steps in order (Verified)

| # | Step | Code |
|:--|:--|:--|
| 1 | Probe waits for the PAS service (`qcom_scm`, built in: `CONFIG_QCOM_SCM=y`, `CONFIG_QCOM_PAS=y`) | `drivers/remoteproc/qcom_q6v5_pas.c:835-836` returns `-EPROBE_DEFER` |
| 2 | Firmware names from DT; the driver tables `adsp.mdt` / `adsp_dtb.mdt` are only defaults | `qcom_q6v5_pas.c:838-850`, tables `:1244-1263` (ADSP) and `:1265-1283` (CDSP) |
| 3 | x1e80100 ADSP: pas_id 1, dtb_pas_id `0x24`, lite_pas_id `0x1f`, lite_dtb_pas_id `0x29`, minidump_id 5, `auto_boot = true`, load_state `adsp`, ssctl 0x14. CDSP: pas_id 18, dtb_pas_id `0x25`, minidump_id 7, load_state `cdsp`, ssctl 0x17 | `qcom_q6v5_pas.c:1244-1283` |
| 4 | rproc name is `sysmon_name`, so `/sys/class/remoteproc/*/name` reads `adsp` and `cdsp` | `qcom_q6v5_pas.c:855` |
| 5 | Memory regions: index 0 image, index 1 DTB. No `iommus` on the node, so `has_iommu` is false and no resource table is fetched from TZ | `qcom_q6v5_pas.c:708-746`, `:862`, `:475-476` |
| 6 | q6v5 init: five IRQs by name, `stop` smem state, `qcom,qmp` (module `qcom_aoss`, `-EPROBE_DEFER` until it probes), interconnect path | `drivers/remoteproc/qcom_q6v5.c:281-380` |
| 7 | Subdevices are added in this order: GLINK, SMD (none: no `smd-edge`), pd-mapper, sysmon, SSR | `qcom_q6v5_pas.c:916-925`; start and prepare run in insertion order |
| 8 | `rproc_add()` logs `<name> is available`; `auto_boot` triggers `request_firmware_nowait()` of the main image, whose callback calls `rproc_boot()` even when the file is missing | `remoteproc_core.c:2342-2349`, `:1669-1703` |
| 9 | `rproc_boot()` logs `powering up`, calls `request_firmware()` again, then `rproc_fw_boot()` logs `Booting fw image <name>, size <n>` | `remoteproc_core.c:1968-1975`, `:1384` |
| 10 | `rproc_start()`: `ops->load` first (`qcom_pas_load`: shuts down the UEFI-loaded "lite" images 0x1f and 0x29, requests the DTB image, `qcom_mdt_pas_load` for it), then **prepare subdevices**, then `ops->start`, then start subdevices | `remoteproc_core.c:1264-1316`; `qcom_q6v5_pas.c:231-262` |
| 11 | Prepare of the pd-mapper subdevice creates auxiliary device `qcom_common.pd-mapper.<rproc index>` **before the DSP starts** | `drivers/remoteproc/qcom_common.c:550-580`, `:603-612` |
| 12 | `qcom_pas_start`: q6v5 prepare (QMP load-state `on`, interconnect vote), proxy power domains, `xo`, DTB `qcom_pas_prepare_and_auth_reset`, `qcom_mdt_pas_load` for the image, carveout map, `qcom_pas_prepare_and_auth_reset`, wait 5 s for the `ready` IRQ | `qcom_q6v5_pas.c:280-358`; `qcom_q6v5.c:79-105` |
| 13 | After `ready`: GLINK subdevice start calls `qcom_glink_smem_register()` (SMEM descriptors, TX FIFO, mbox channel 0); a failure fails the whole start | `qcom_common.c:216-223`; `drivers/rpmsg/qcom_glink_smem.c:227-368` |
| 14 | Handover IRQ releases `lcx`/`lmx` (or `cx`/`mxc`/`nsp`) proxy votes and the interconnect vote | `qcom_pas_handover`, `qcom_pas_start` `qcom_q6v5_pas.c:391-402`; `qcom_q6v5.c:198-212` |
| 15 | `rproc_start()` logs `remote processor <name> is now up` | `remoteproc_core.c:1315` |

## 3. In-kernel services (Verified)

| Service | Code |
|:--|:--|
| pd-mapper starts on the auxiliary device, registers QMI server `SERVREG_LOC` (service 64, version `0x101`, instance 0) on the local QRTR node | `drivers/soc/qcom/qcom_pd_mapper.c:681-734`, `:736-761` |
| Platform table: `qcom,x1p42100` and `qcom,x1e80100` use `x1e80100_domains`: `msm/adsp/audio_pd` (with `avs/audio`), `msm/adsp/root_pd`, `msm/adsp/charger_pd`, `msm/adsp/sensor_pd`, all instance 74, and `msm/cdsp/root_pd` instance 76; every domain also answers service `tms/servreg` | `qcom_pd_mapper.c:609-616`, `:666-667`, `:253-312`, `:106-130` |
| The mapper's lookups are `pr_debug` only, so they are invisible without dynamic debug | `qcom_pd_mapper.c:194,200` |
| QRTR name service is in `qrtr` (`net/qrtr/ns.c`); the GLINK channel `IPCRTR` is bound by `qrtr_smd` | `net/qrtr/smd.c:60-90`; `drivers/rpmsg/qcom_glink_native.c:1629-1700` (remote-open creates the rpmsg device) |
| PDR client: `pdr_handle_alloc()` registers a locator lookup (service 64, version 1, instance 1); `pdr_add_lookup()` queues a lookup; the locator asks `tms/servreg` for the domain list, then looks up the notifier (service 66, instance from the domain, 74 for ADSP), then registers a listener | `drivers/soc/qcom/pdr_interface.c:638-702`, `:509-546`, `:392-496`, `:113-157`, `:191-213` |
| **A PDR lookup error other than `-ENXIO` deletes the lookup and reports `SERVREG_LOCATOR_ERR`; nothing retries it** | `pdr_interface.c:441-457` |
| pmic_glink platform device creates the three auxiliary devices `ucsi`, `altmode`, `power-supply` at probe (it does not wait for the ADSP) and adds the PDR lookup `tms/servreg` / `msm/adsp/charger_pd` | `drivers/soc/qcom/pmic_glink.c:299-358`, `:392-398` |
| The rpmsg channel `PMIC_RTR_ADSP_APPS` binds `pmic_glink_rpmsg_probe`; clients get state `UP` only when PDR is `UP` **and** the endpoint exists | `pmic_glink.c:213-234`, `:246-265`, `:283-287` |
| battmgr (`qcom_battmgr`) registers battery, AC, USB and wireless supplies at probe, before the ADSP answers; values appear when the PDR state is `UP` | `drivers/power/supply/qcom_battmgr.c:1628-1727`, `:1602-1612` |
| UCSI (`ucsi_glink`) reads `reg` and `orientation` GPIO of each connector child (max 3), allocates the PMIC_GLINK_OWNER_USBC client | `drivers/usb/typec/ucsi/ucsi_glink.c:394-475` |
| Altmode (`pmic_glink_altmode`) needs typec-mux, retimer and orientation-switch for each connector (`-EPROBE_DEFER` until `ps883x` is up) | `drivers/soc/qcom/pmic_glink_altmode.c:570-700` |
| FastRPC rpmsg driver binds `fastrpcglink-apps-dsp`, needs `label`; creates `/dev/fastrpc-adsp` (secure by default unless `qcom,non-secure-domain`, which both nodes set) and, for the CDSP, both a secure and a non-secure node | `drivers/misc/fastrpc.c:2536-2640` |
| GPR/APR (audio): `adsp_apps` channel; `q6apm` probe asks the SPF state (`APM_CMD_GET_SPF_STATE` = `0x01001021`) and waits 5 s | `sound/soc/qcom/qdsp6/q6apm.c:143-152,886`; `audioreach.c:617-623`; `audioreach.h:42` |
| PD-charger ULOG, a manual-load diagnostic: rpmsg `PMIC_LOGS_ADSP_APPS`, requests logs every second and emits tracepoint `pmic_pdcharger_ulog:pmic_pdcharger_ulog_msg` | `drivers/soc/qcom/pmic_pdcharger_ulog.c:20-170`, `pmic_pdcharger_ulog.h:6-14` (`CONFIG_QCOM_PMIC_PDCHARGER_ULOG=m`) |

## 4. What each subsystem must expose

| Function | Needs from the ADSP | Needs from the kernel | Needs from the CDSP |
|:--|:--|:--|:--|
| Battery (qcom_battmgr) | GLINK channel `PMIC_RTR_ADSP_APPS`; PD `msm/adsp/charger_pd` registered with the servreg notifier (service 66, instance 74) | pd-mapper answering `tms/servreg` with `msm/adsp/charger_pd`; `qrtr` + `qrtr_smd` for the ADSP's `IPCRTR`; `pmic_glink` + `qcom_battmgr` | nothing |
| Charging and AC/USB supplies | the same channel and PD | the same | nothing |
| USB-C (UCSI, altmode) | the same channel; owner USBC and USBC_PAN messages | the same, plus connector DT, orientation GPIOs, `ps883x` retimers, DWC3 | nothing |
| Audio (unused, S1) | `adsp_apps` channel, PD `msm/adsp/audio_pd` with service `avs/audio` | `gpr`, `q6apm`, `q6prm`, no sound card | nothing |
| Sensors | PD `msm/adsp/sensor_pd`, fastrpc (userspace) | none now | nothing |
| NPU | nothing | nothing | `IPCRTR`, `fastrpcglink-apps-dsp` on the CDSP edge |

## 5. Windows evidence for the same functions (Verified)

- ADSP INF `surfacepro_ext_adsp8380.inf` (SHA-256 `7e239e432b5eff65e16b31fe1ef9deef701a46c97ca7aa625c01cc61471b4372`): image `qcadsp8380.mbn` (`:128`), DTB `adsp_dtbs.elf` (`:159`), `IsDTBImageSupported = 1` (`:157`), UEFI-loaded lite image TZ ids `0x1F` and `0x29` with action "Need Restart" (`:139-143`), `IgnoreWdogEnabled = 1` "WDOG bite workaround" (`:135`), `ADSP` memory reservation `0x3A00000` and `ADSP_DTB` `0x11000` (`:195`, `:196`), a resource bin `RADS.bin` (`:182`, 1401 bytes, catalogued `data`, not needed by Linux: no `iommus`, step 5), three PDs mapped to the ADSP: audio, charger, sensor (`:205-207`).
- CDSP INF `qcnspmcdm_ext_cdsp8380.inf`: `ImagePath1 = qccdsp8380.mbn`, `DTBImagePath1 = cdsp_dtbs.elf`, `CDSP` reservation `0x2000000` (matches `cdsp_mem`).
- Live inventory (`live-inventory/pnp-present.json`): only one battery-class device, "Surface Battery" (SSAM, `surfacebattery`); a UCM-UCSI ACPI device `ACPI\USBC000` (driver `qcusbcucsi8380`); "Qualcomm Power Management PMIC GLink Device" `ACPI\QCOM0C8E`; PD service registry `ACPI\VEN_QCOM&DEV_06DF`; PIL `ACPI\VEN_QCOM&DEV_06E0`; FastRPC `ACPI\QCOM0C5C`. Inference: on Windows the battery gauge reaches the OS through SSAM, and the USB-C PD stack and charger through the ADSP.
