# dsp-subsystems

## 1. Summary

The ADSP and CDSP remote processors provide GLINK/QRTR services; ADSP carries the charger protection domain and UCSI transport. Status: `blocked` for the M9 CDSP fix: M8 confirms working ADSP charger transport and D23, but CDSP IPCRTR/FastRPC still fail and REA MCP rejects the required binary investigation.

No kernel fix is claimed or released. The local changes improve the read-only collector, correct stale battery policy and document exact tool/image requests. They remain uncommitted for the orchestrator (D24).

Current evidence: [M8 and M9](evidence/2026-10-29-m8-and-m9.md), [Windows loader inputs](evidence/2026-10-29-windows-loader-inputs.md). Earlier static references: [PAS path](evidence/2026-10-28-pas-path-static.md), [ELF headers](evidence/2026-10-28-blob-headers.md), [M5](evidence/2026-10-28-m5-device-log.md). The 2026-10-29 evidence supersedes earlier policy advice and unsupported conclusions about the Windows resource bins. Plan: [test-plan.md](test-plan.md). Collector: [dsp-subsystems.sh](collector/dsp-subsystems.sh).

## 2. Hardware

All values below are Verified **Linux/source** facts, not Windows decompilation results.

| Item | Value | Citation |
|:--|:--|:--|
| ADSP | `qcom,x1e80100-adsp-pas`, `0x06800000`, PAS 1, DTB PAS `0x24`, lite IDs `0x1f`/`0x29` | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:4274`; `drivers/remoteproc/qcom_q6v5_pas.c:1244-1263` |
| CDSP | `qcom,x1e80100-cdsp-pas`, `0x32300000`, PAS 18, DTB PAS `0x25` | `hamoa.dtsi:8944`; `qcom_q6v5_pas.c:1265-1283` |
| ADSP reserved memory | image `0x87e00000` +`0x3a00000`; DTB `0x8b800000` +`0x80000` | `hamoa.dtsi:578-586`; ELF-header evidence |
| CDSP reserved memory | image `0x8b900000` +`0x2000000`; DTB `0x8d900000` +`0x80000` | `hamoa.dtsi:588-596`; ELF-header evidence |
| GLINK | ADSP label `lpass`, remote PID 2, IPCC client 3; CDSP label `cdsp`, remote PID 5, client 6; signal 0 | `hamoa.dtsi:4310-4318,8982-8990`; `include/dt-bindings/mailbox/qcom-ipcc.h:10-22` |
| SMEM | descriptor item 478, FIFOs 479/480; 32-byte descriptor, 16 KiB TX FIFO | `drivers/rpmsg/qcom_glink_smem.c:34-36,273-312` |
| Service domains | ADSP audio/root/charger/sensor instance 74; CDSP root instance 76 | `drivers/soc/qcom/qcom_pd_mapper.c:609-616`; five Windows JSN maps, static PAS evidence |

## 3. Windows

| DriverStore package | Established role/input |
|:--|:--|
| `surfacepro_ext_adsp8380` | ADSP image, DTB, lite-image IDs, `RADS.bin`, service maps and user libraries |
| `qcnspmcdm_ext_cdsp8380` | CDSP image/DTB pair, matching reservations, service map and user libraries |
| `qcsubsys8380` | Subsystem framework; code order still requires REA |
| `qcsubsys_ext_cdsp8380` | INF plus `RCDS.bin`, no SYS; configures interface requirements, DTB support, shutdown and resource input |
| `qcpil`, `qcpilext8380` | Loader SYS and configuration-only extension; authentication/reset order requires REA |
| `qcsubsysthermalmgr` | Thermal client driver; any boot prerequisite remains TBD; no limit changes permitted |
| `qcadsprpc8380`, `qcadsprpcd8380` | FastRPC kernel/client service infrastructure; OPEN versus later process/file service remains to be established |
| `qcpdsr`, `qcipcrouter8380`, `qcglink8380`, `qcpmicglink8380`, `qcusbcucsi8380` | Service registry, QRTR, GLINK and PMIC/UCSI transport |
| `surfacebattery` | SAM battery; ACPI `PMBM._STA` disables the other battery manager (D23) |

Catalog-checked hashes, decoded INF line citations and ACPI dependency lists are in the Windows evidence. ACPI/INF dependencies do not prove an ADSP-before-CDSP boot order. `RADS.bin`/`RCDS.bin` are subsystem resource inputs; no Linux file request is known, but their resource operations have not been reconciled with Linux. Their consumer must not be called userspace without REA evidence.

REA MCP `binary_session` failed before any analysis: `MCP tool call requires approval, but approval policy is never`. No binary was opened, function decoded or `evidence_id` produced. The configured server also lacks forced `REA_GHIDRA_LANGUAGE_ID` (R-S1). All ARM64 SYS analysis must use `AARCH64:LE:64:v8A` under `flock out/.ghidra.lock`.

## 4. Linux 7.3

The stack is `qcom_q6v5_pas`, `qcom_glink_smem`, `qrtr`/`qrtr_smd`, in-kernel `qcom_pd_mapper`, `pdr_interface`, `pmic_glink`, `ucsi_glink`, `pmic_glink_altmode` and `fastrpc`. No userspace pd-mapper, modem rmtfs or tqftpserv service is needed for these DSPs. `qcom_battmgr` stays blocked by image policy D23.

The [static PAS path](evidence/2026-10-28-pas-path-static.md) traces probe to services. DT firmware strings are in `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1038-1050`. Linux loads DTB before authenticating/resetting DTB and main image, waits for ready, then starts GLINK; the mapper is prepared before DSP start. There is no established missing Windows step yet.

M8 has both DSPs `running`. ADSP's PMIC, QRTR and FastRPC channels bind; charger/audio PDR indications are UP, QRTR node 5 serves the ADSP, and both UCSI ports exist. The APM SPF-state request still times out; working transport does not prove audio health (S1: sound and speaker bus stay off).

CDSP advertises five channels and its GLINK IRQ fires six times, but IPCRTR and FastRPC fail with -12 after approximately five seconds. The wait is consistent with `qcom_glink_create_remote()` at `drivers/rpmsg/qcom_glink_native.c:1288-1316`; `rpmsg_core.c:454-458` masks endpoint failure as -ENOMEM. Exact handshake failure remains unproven without tracing. No carve-out, PAS ID, mailbox or timeout change is justified yet.

D20 early PAS and the four paired firmware files stay as currently integrated. BTF stays enabled. No kernel patch or build was made this session.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| CDSP IPCRTR/FastRPC OPEN failure | Restore REA MCP (R-S1), compare actual Windows procedures, collect early GLINK handshake (R-I2), then port the demonstrated minimum |
| Missing M8 default trace | M9 diagnostic entry or boot arguments active before `qcom_glink` loads; refreshed collector reports event enables, overruns and each edge separately |
| ADSP SPF-state timeout | Audio owners investigate with speakers off; do not disable ADSP charger services |
| Charging behavior not established | M8 AC is offline; collect SAM/UCSI while a known charger is attached during the next scheduled boot; no limit writes |
| UPower connection refused | Image/ec-sam inspect unit state and journal; collector now captures both without starting a service |
| Battery double registration / writable battmgr thresholds | Closed by D23 in M8: only SAM BAT1, battmgr absent, UCSI retained; keep policy and L0 checks |
| Firmware names, hashes and ELF spans | Reconfirmed statically on 2026-10-29; no firmware correction requested |

## 6. Open questions

| Question | Grade and next evidence |
|:--|:--|
| Which GLINK handshake operation fails, and does CDSP consume APPS TX? | TBD: early VERSION/OPEN/ACK trace plus Windows GLINK/resource initialization evidence |
| Does Windows require a boot/resource notification before ACK? | TBD: actual `qcsubsys`, PIL and FastRPC procedures; interface lists alone do not establish it |
| Do resource-bin operations differ from Linux power/interconnect setup? | TBD: RCDS parser in REA; keep data out of the disassembler |
| Does ADSP SPF become ready later? | TBD: read-only log evidence; audio owners |
| Does SAM report charging with a charger attached? | TBD: M8 only establishes discharge; D23 remains current |
| Is early PAS necessary for USB-C-root boot? | Hypothesis retained from M5; optional existing no-early-PAS entry only if an already planned test needs it |

## 7. Acceptance

ADSP: consistently `running`, bound IPCRTR/PMIC channels, charger PDR UP and usable UCSI; SAM BAT1/ADP1 track actual charging/discharging with no battmgr or exposed battmgr charge thresholds. M8 establishes transport and discharge; charging remains open. CDSP: bound IPCRTR/FastRPC, advertised QRTR services and completed handshake without five-second probe failures. M8 fails that requirement. A source patch additionally needs build/checkpatch and independent cross-check before `sw-ready`; `pass` remains the orchestrator's decision.

## 8. Requests

- **sources** (R-S1, blocking): restore a usable REA MCP connection; its first status call is approval-gated under policy `never`. Also set the MCP process environment `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A` before opening any listed SYS; preserve Ghidra/JDK paths, adequate heap and startup timeout, and hold `flock out/.ghidra.lock` throughout. Do not route around the approval failure. Target hashes and exact analysis questions are in the Windows evidence section 3; snapshots belong under `out/rea/dsp-subsystems/`. This worker cannot edit tool setup.
- **image** (R-I1): refresh `/etc/sp11-log-collector.d/dsp-subsystems.sh` from the owned collector. It fixes unbound-driver output and adds IRQ counts, trace configuration/overruns, separate CDSP/ADSP handshake rows, D23 modprobe dry run and read-only UPower health. Include it in the next ISO; no separate device boot requested.
- **image** (R-I2): M8 default `debug` lacks DSP tracing; `usbdbg` already contains the requested arguments. For the next planned DSP evidence boot, select that entry or include `qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M` in the tested entry. Verify them in the resulting `cmdline.txt` and the event enables in the extra collector. Tracing must start at module load; enabling it after the timeout loses the handshake. No collector may enable/clear tracing or rebind/restart a DSP.
- **image / ec-sam** (R-I4/E1): retain D23 blacklist, `install ... /usr/bin/false`, initramfs omission and L0 assertions. M8 closes double registration. Diagnose UPower's connection refusal using the new unit/journal reads and capture attached-charger SAM/UCSI state in the next scheduled test. No charge-control write, forced role or limit adjustment.
- **soc-boot** (R-S2): once REA is usable, supply catalog-checked ARM64 `qcglink8380` evidence for version/features, OPEN/ACK ordering, SMEM descriptor/FIFO layout, APPS-to-CDSP doorbell and resource/wake notifications. Request is read-only; no shared-file change or device action.
- **audio owners** (A1): M8 ADSP audio PDR is UP but `APM_CMD_GET_SPF_STATE` still times out; transport success is not audio acceptance. Keep sound/SoundWire speakers off.
- **kernel** (R-K1): append `hardware/dsp-subsystems/patches/0001-rpmsg-glink-log-open-ack-timeout.patch` to `kernel/series` as series rev 7, after the usb-typec 0002 entry. Read-only diagnostic: ratelimited `sp11-glink:` log lines for GLINK VERSION/VERSION_ACK/OPEN/OPEN_ACK/RX_INTENT, the 5 s OPEN_ACK timeout and `qcom_glink_create_ept()` NULL returns; no behaviour or Kconfig change. Checked: `git apply --check` on v7.3 plus the full current series, `checkpatch --strict` clean except the intentionally absent Signed-off-by. Remove it from the series once the handshake evidence is captured. Collector greps are in `evidence/2026-10-29-rea-windows.md` section 7.4.
- **kernel** (R-K3): append `hardware/dsp-subsystems/patches/0002-rpmsg-glink-log-fifo-indices-on-open-ack-timeout.patch` after 0001 (series rev 8, read-only diagnostic: logs SMEM FIFO head/tail words on the OPEN_ACK timeout). Checked: checkpatch clean except absent Signed-off-by; `git apply --check` on v7.3 plus the full series. Next boot should also add `smp2p:*,remoteproc:*` to `trace_event=` (R-I2) and the collector reads of remoteproc debugfs `trace0`/`resource_table` (see `evidence/2026-10-30-m10-cdsp.md` section 4).
- **firmware / kernel**: no firmware replacement or functional patch to integrate. Keep paired Denali blobs, existing PAS configuration and BTF. Revisit after R-S1 and handshake evidence, then request independent cross-check for new hardware values.

Earlier E1 advice to hide battmgr in UPower and O1 advice to choose a threshold policy are superseded by D23. R-I3 (optional no-early-DSP comparison) is not required for M9 and must not trigger another device reboot on its own.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-28: PAS/service path, ELF headers and M5 evidence; both DSPs running, CDSP handshake failure, duplicate battery and writable-threshold findings; initial collector and test plan. Status `testing`.
- 2026-10-29: M8 confirms ADSP charger/QRTR health, persistent CDSP failure, D23 SAM-only battery and discharge; UPower unavailable and no default GLINK trace. Catalog/INF/ACPI comparison recorded, resource-bin consumer claims corrected, read-only collector/test plan refreshed. REA MCP is approval-gated and lacks forced language; status `blocked`, no kernel fix claimed, changes uncommitted (D24).
- 2026-10-30: diagnostic patch 0001 (`sp11-glink:` GLINK logging) written; kernel request R-K1 added. No behaviour change, not committed.
- 2026-10-30: M10 evidence: CDSP acks VERSION and opens five channels but never acks our OPEN (ADSP edge fine); DT equals hamoa; Apps-to-CDSP doorbell worked for the first messages; no fix established; diagnostic patch 0002 (FIFO indices) written. See `evidence/2026-10-30-m10-cdsp.md`. Not committed.
