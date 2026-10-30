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

## 6. Second pass (2026-10-30): decompilation attempt

Both binaries re-opened one at a time in REA (Ghidra 12.1.4, language
auto-from-header arm64, deviation from protocol section 9.2 still open); SHA-256
matched the catalog for `qcsubsys8380.sys` (`4ce9bc81...a995be`) and
`qcglink8380.sys` (`31a26129...103253583`). The state-name strings have no code
xrefs: they sit in an event/state name table used for tracing (value, kind,
name pointer records in `.rdata`). The dispatcher is therefore table driven and
cannot be found by string xrefs.

### 6.1 qcsubsys8380.sys

Verified:

- The state machine is hierarchical (compound states `COMP_LOADING`,
  `COMP_OPERATING`, `COMP_PDRESTARTING`, `COMP_APSS_INITIATED_SSR`, ...). Its
  transitions live in `.data` as (state, event, next state) triples. The event
  name table gives the full event vocabulary, including
  `SMP2P_ERR_HDL_RDY`, `SMP2P_PWR_CLK_RDY`, `SMP2P_QB_RDY`,
  `ALL_SMP2P_EVENTS_RDY`, `SMP2P_DS_ACK`, `QB_COMPLETED`,
  `ALL_INTERFACES_OPENED`, `RPEN_CONNECTION_READY`, `LOAD_IMAGE_SUCCESS`,
  `QMI_SERVICES_INITIALIZED`, `SMP2P_ERRFATAL`, `SMP2P_SHUTDOWN_ACK`.
- Windows waits for three separate SMP2P ready events (error handler, power/clock,
  QB) and a combined "all ready" event, plus a data-service ack (`WAIT_FOR_DS_RDY`).
  Linux `qcom_q6v5` waits for one `ready` interrupt and handles `handover` and
  `stop-ack` separately; it has no counterpart of `QB_RDY` or `DS_ACK`.
- The SMP2P channel is prepared before the load wait
  (`PREPARE_SMP2P_CHANNEL_INIT`, `WAIT_FOR_SMP2P_LOAD_EVENTS`). The preparing
  routine registers a Subsystem-to-Apps and an Apps-to-Subsystem SMP2P context
  and waits on each with a 1 s timeout (code constant -10 000 000 in 100 ns
  units); on timeout it assumes the subsystem crashed or hung and proceeds.
- Sysmon is not QMI sysmon here: the SSR hooks are named per subsystem
  (`ssr:cdsp:before_shutdown`, `ssr:cdsp:after_shutdown`), i.e. glink_ssr
  notifications around shutdown. Only SHUTDOWN has before/after strings; the
  `SYSMON_BEFORE/AFTER_POWERUP` states exist but no powerup string was found.
- SMP2P entries used on the apps side are named `master-kernel` and `slave-kernel`.

Unknown (not established, table decode was only partial): the exact order of
LOAD_IMAGE, AUTH_IMAGE, SYSMON_AFTER_POWERUP, INITIALIZE_QMI_SERVICES and the
meaning of events in each transition. Decoded triples around
`CHECK_AND_WAIT_FOR_INTERFACES` -> `CHECK_AND_WAIT_FOR_RPEN_READY` ->
`CHECK_AND_MARK_IMAGE_AS_PRELOADED` and `IS_DTB_IMAGE_SUPPORTED` ->
`LOAD_DTB_IMAGE` -> `LOAD_FTD_PATH_MAPPINGS` are plausible, but the state and
event numbering was not validated against the compound-state records, so they
are Inference only. The bit positions of ERR_HDL/PWR_CLK/QB in the SMP2P entry
were not recovered.

Inference: ERR_HDL_RDY corresponds to Linux `ready`; PWR_CLK_RDY may correspond
to Linux `handover`; QB_RDY has no known Linux or DT equivalent.

### 6.2 qcglink8380.sys

Verified (strings): the core is Qualcomm GLINK `rel 10.9` with an SMEM transport
and a separate SMP2P transport-interrupt layer (`smp2pi_negotiate`: negotiation
state is updated per remote). The core also supports intentless data
(`Invalid RX Data intentless cmd`), RX intent queueing per channel after open
(`Queued RX intent on channel ...`), a control channel and an SSR channel
(`SSR channel open succeed/failed`), and drops open acks for closed channels.

Unknown: GLINK VERSION/FEATURES numbers, the order of open/open-ack/intent
commands and the feature mask were not decompiled; no function was reached.

### 6.3 Comparison and decision

- The Denali `remoteproc_cdsp` node already carries wdog, fatal, ready,
  handover, stop-ack and the GLINK edge (section 4). Nothing in this pass shows a
  missing property or memory region.
- A gap in Linux that Windows demonstrates: Windows treats QB and data-service
  readiness as extra boot gates. Whether the CDSP firmware raises them and
  whether the GLINK edge depends on them is Unknown.
- No missing step is established, so no patch was written
  (`hardware/dsp-subsystems/patches/` does not exist).

### 6.4 Next evidence

1. Decode the per-compound transition records (header triple plus event rows) to
   fix the LOADING sequence; verify numbering with the event table above.
2. Decompile the routine that handles `ALL_SMP2P_EVENTS_RDY` and recover the SMP2P
   bit masks for ERR_HDL/PWR_CLK/QB.
3. Capture the CDSP SMP2P `slave-kernel` entry value in a Linux boot log to see
   which bits the firmware raises.
4. Capture the first GLINK SMEM commands (VERSION, SET_VERSION_ACK, OPEN) on Linux.
