# REA pass on Windows subsystem drivers (2026-10-29)

Scope: string-inventory level only. No procedure was decompiled, so no call
order is established. Grades: Verified = observed in the binary string
inventory at the cited address; Inference = reasoned from names.

Tool setup deviation (protocol section 9.2): the REA MCP profile reported
`language_id=auto-from-header` (not forced). Ghidra chose `arm64` from the PE
header. The server environment could not be changed from this worker; the
sources owner must still set `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`.
One binary was open at a time and closed before the next.

## 1. qcsubsys8380.sys

SHA-256 `4ce9bc81...a995be`, Ghidra 12.1.4, evidence ids
`ev_007b2b08...`, `ev_27129a90...`.

Verified (enum name strings, `0x14005bf60`-`0x14005d478`):

- The device state machine has states `WAIT_FOR_SMP2P_LOAD_EVENTS`,
  `PREPARE_SMP2P_CHANNEL_INIT`, `CHECK_AND_WAIT_FOR_INTERFACES`,
  `CHECK_AND_WAIT_FOR_RPEN_READY`, `WAIT_FOR_VOL_STARTUPAPP_COMPLETE`,
  `LOAD_FTD_PATH_MAPPINGS`, `IS_DTB_IMAGE_SUPPORTED`, `LOAD_DTB_IMAGE`,
  `AUTH_DTB_IMAGE`, `LOAD_IMAGE`, `AUTH_IMAGE`, `SYSMON_BEFORE_POWERUP`,
  `SYSMON_AFTER_POWERUP`, `INITIALIZE_QMI_SERVICES`, `REQUEST_P0`/`P2`,
  `GO_NO_GO`, `RPE_READY_FOR_COMMANDS`.
- Per-subsystem keys exist: `CdspRestartEnabled`, `AdspRestartEnabled`,
  `DTBImagePath1`, `UefiLoadedDTBImageTZProcID`, `IsDTBImageSupported`.

Inference (names only; enum order is not execution order):

- Windows waits for the RPE/RPEN interface (the GLINK/IPC-router side) to be
  ready around the image load, and runs SYSMON power-up hooks before and after
  start. Linux has no equivalent explicit "interfaces ready" gate before
  starting the CDSP GLINK edge.
- Windows loads and authenticates the DTB first, then the main image, matching
  Linux `qcom_pas_load/start` ordering (consistent with existing evidence).

Unknown: transition order, what `SYSMON_AFTER_POWERUP` sends, what RCDS fields
the parser consumes.

## 2. qcglink8380.sys (package bb5db2dec7306719)

SHA-256 `31a26129...103253583`, evidence id `ev_bececfea...`.

Verified:

- Full Qualcomm GLINK core with intents: `GLINK_EVENT_CH_OPEN`,
  `CH_OPEN_ACK`, `CH_Q_RX_INTENT`, `CH_TX_INTENT_ID`, `RM_CH_OPEN`.
- A GLINK SSR channel (`glink_ssr`) and SMEM version checks
  (`smem_init: major version ... does not match`; TOC version asserted 1).
- RPE client init requires callbacks including `GetMemoryRegionCallback` and
  `SubsystemCheckStateCallback`.

Inference: Windows queues RX intents on channels as part of open. Linux
`qcom_glink_native` relies on the remote requesting intents. A CDSP that never
ACKs OPEN is not explained by this; the failure may precede the OPEN
(handshake VERSION/FEATURES) and still needs a GLINK trace.

## 3. Not reached

`qcpil`, `qcadsprpc8380`, `qcadsprpcd8380` and `qcsubsys_ext_cdsp8380` (INF
and RCDS data) were not opened in this pass. Firmware names, carve-outs and
domain IDs were therefore not re-verified against Windows binaries; the INF
facts in `2026-10-29-windows-loader-inputs.md` stand.

## 4. Comparison with Linux 7.3 and DT

- DT `remoteproc_cdsp` (`hamoa.dtsi:8944`) already has wdog, fatal, ready,
  handover, stop-ack SMP2P, `qcom,qmp`, power domains cx/mxc/nsp, NSP NoC
  interconnect and the Denali firmware pair. No missing property was found.
- No Windows-derived minimal fix is established. No patch is proposed.

## 5. Next evidence

Decompile the state-machine dispatcher in `qcsubsys8380` (xrefs to the state
table, not the strings) to get the real order around `SYSMON_*`; decompile the
RPEN-ready path in `qcglink8380`; capture an early Linux GLINK VERSION/OPEN
trace.
