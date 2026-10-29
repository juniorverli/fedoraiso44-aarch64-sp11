# Windows loader inputs and remaining REA work

Grades: static INF/ACPI facts below are Verified at their cited locations.
Function behavior, runtime order, SMEM layout and GLINK wire equivalence remain
TBD. No Windows code was disassembled in this session; the MCP gate is recorded
in `2026-10-29-m8-and-m9.md` section 4.

## 1. Catalog check

Paths are relative to `sources/windows/DriverStore/`. Each file was looked up in
`sources/binary-catalog.tsv` and its SHA-256 reproduced on 2026-10-29. These are
candidates for inspection, not a claim that every duplicate package is active.
The only permitted Ghidra language for each SYS below is **`AARCH64:LE:64:v8A`**.

| File | SHA-256 |
|:--|:--|
| `qcsubsys8380.inf_arm64_7ea7d71125b6b61b/qcsubsys8380.sys` | `4ce9bc816560d24a8f601485b6119daccaabae243cb58354aea07a1edca995be` |
| `qcpil.inf_arm64_b70a9f8db2e352b7/qcpil.sys` | `49a93b3e9033808d887a7b5bb72cbc89a6b3a28a4c9c29b5062753fe79fbe72f` |
| `qcsubsysthermalmgr.inf_arm64_e311ab7034cc5a71/qcSubsysThermalMgr.sys` | `f0264cb3945dc1df35e791c0ccd04a1cfd8c66b2a00675b112599ebb44b5ce77` |
| `qcadsprpc8380.inf_arm64_8a9317173b863cf9/qcadsprpc8380.sys` | `ca36e7d23c08df7ba61aa4b06d37c7d2ff105def4d218d62c54b6b217878da26` |
| `qcadsprpcd8380.inf_arm64_14d6e3e3fd3efb26/qcadsprpcd8380.sys` | `0ae1a0ea27eb5312dd585d8e60b0e008f2800bed7ead623ef7851673f785522b` |

`qcsubsys_ext_cdsp8380` and `qcpilext8380` have **no SYS to decompile**:

| File | SHA-256 | Interpretation |
|:--|:--|:--|
| `qcsubsys_ext_cdsp8380.inf_arm64_6bc7c16c9336f70f/qcsubsys_ext_cdsp8380.inf` | `02fcfe49a3e8e23cfcec4ee8e135ff85c59a2b2ba38bd800b10b531d14a7ef99` | UTF-16 text |
| `qcsubsys_ext_cdsp8380.inf_arm64_6bc7c16c9336f70f/RCDS.bin` | `7e9e307435468e01d4bf746a1028466f60f4a83268fbc4f194926a93b2b2267c` | Structured data; never disassemble |
| `qcpilext8380.inf_arm64_0f880b3811079b55/qcpilEXT8380.inf` | `81d4acb5005aae44769b8c9e03fcfd0ecf87b87c510cbd02657856c95203084b` | UTF-16 text |

`qcadsprpc*` also contains hybrid ARM64X libraries. These have not been inspected;
inspect the native ARM64 half only, after checking the selected row. Do not
substitute the older duplicate SYS paths without documenting the chosen version.

## 2. What the text establishes

INF line numbers refer to UTF-16 decoded text, one-based.
Additional source hashes used below:

| Source | SHA-256 |
|:--|:--|
| `qcsubsys8380.inf_arm64_7ea7d71125b6b61b/qcsubsys8380.inf` | `28d31d6aec174a43630bd86e3a25e8ef72819611c8ff2f121a8424ac30cb9374` |
| `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/qcnspmcdm_ext_cdsp8380.inf` | `814b352f5ce3deeab3aaec62273d9c1f3ecddb94284e478671cd590074b44a2b` |
| `sources/windows/live-inventory/acpi/dsdt.dsl` | `8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede` |

- `qcsubsys_ext_cdsp8380.inf:62-89`: CDSP declares restarting GLINK clients and
  PIL-TZ, FastRPC and GLINK interfaces. It enables DTB support, requests graceful
  shutdown/SSCTL, skips UEFI-loaded-subsystem detection, and sets the watchdog
  workaround flag. These are configured requirements, not a proven call sequence.
- The same INF `:95-107` sets `WaitForVolStartupAppComplete=1`, selects
  `PathMappingKeyName=DefaultV1` and passes `Resources/BinaryPath=RCDS.bin` to the
  subsystem device. `:115-117` identifies thermal QMI device `cdsp_sw`, instance
  `0x43`. No charging or thermal policy change follows from this metadata.
- `qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/qcnspmcdm_ext_cdsp8380.inf:103-126`
  supplies `qccdsp8380.mbn` plus `cdsp_dtbs.elf`, image alignment 1 MiB, DTB
  alignment 64 KiB, reservations `0x2000000` and `0x9000`. These fit the Linux
  reserved regions (previous header evidence). `DefaultV1` versus the older
  library mappings under `Default` merits checking for later FastRPC file service;
  it is not evidence that GLINK OPEN needs user libraries.
- `qcpilEXT8380.inf:247-260` sets hypervisor protection, LCPDare support and IMEM
  base/offset `0x146aa000`/`0x94c`. Linux equivalence is TBD; a registry flag is
  not evidence Linux should copy an undocumented operation.
- `qcsubsys8380.inf:115-118` enables ADSP/CDSP restart handling. This does not
  justify ignoring Linux watchdogs.
- ACPI `sources/windows/live-inventory/acpi/dsdt.dsl:51672-51684` lists ADSP
  dependencies PEP, PIL, GLINK, IPC router, RPE, SSDD and FastRPC. `:51862-51874`
  lists CDSP dependencies PEP, PIL, GLINK, IPC router, RPE and SSDD. These are
  readiness dependencies; neither list establishes an ADSP-before-CDSP boot rule.
  `:51880-51889` gives CDSP watchdog interrupt 0x262, consistent with Linux
  GIC SPI 578 plus 32. Do not confuse this watchdog with the GLINK mailbox.

Correction to the earlier dossier: `RADS.bin` and `RCDS.bin` are Windows subsystem
resource inputs. Their absence from Linux's `request_firmware()` paths is
Verified; that alone does **not** establish that every resource operation they
describe is unnecessary, or that userspace is their consumer. Inspect the
resource parser in `qcsubsys8380.sys` before deciding which operations Linux
already supplies through power domains, interconnects and remoteproc.

## 3. Exact next REA tasks (R-S1)

Sources owner must first restore an MCP connection usable in this session and
configure its process with `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`, the existing
Ghidra/JDK paths, sufficient heap and startup timeout. Hold `flock out/.ghidra.lock`
for the entire server/analysis lifetime. Do not change global configuration from
this worker, launch an unforced provider or bypass the rejected approval call.
Keep all snapshots/evidence bundles in `out/rea/dsp-subsystems/`.

1. Open each selected SYS with provider `ghidra`, call `list_procedures` first,
   then follow actual procedure addresses and string references. Record path,
   SHA-256, forced language, function address and `evidence_id` per conclusion.
2. In `qcsubsys8380`: find resource parsing, interface readiness, DTB/PIL load,
   watchdog handling, GLINK/RPE notification and ready/handover paths. Resolve
   the RCDS resource schema as data using its actual parser.
3. In `qcpil`: establish DTB-versus-image authentication/reset ordering and PAS
   arguments, memory setup, and lite-image shutdown. Compare with
   `qcom_pas_load/start`, not just the INF's ordering of keys.
4. In `qcadsprpc8380` and `qcadsprpcd8380`: separate the channel OPEN from later
   process creation and remote file service. Prove whether any preliminary
   notification is needed before CDSP can ACK; do not infer it from an interface
   dependency alone.
5. In `qcSubsysThermalMgr`: establish whether it is a post-QRTR client or has a
   prerequisite boot handshake. Read policy only; S6 forbids raising limits.
6. GLINK wire/SMEM/IPCC parameters may require `qcglink8380.sys` (soc-boot owner).
   Catalog-check it and request the owner's evidence for the same handshake,
   version/features, descriptor/FIFO layout, doorbell and any resume/wake call.
   Discard any procedure with bad-instruction markers.

Only then propose a minimal Linux/image change, with independent cross-check of
new hardware values before `sw-ready`. Existing Linux DT constants are not
Windows-derived verification. No fix is claimed while these tasks are open.
