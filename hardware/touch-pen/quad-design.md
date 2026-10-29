> Session 3 supersedes the proposed implementation below. See
> [working-reference evidence](evidence/2026-10-29-working-reference.md)
> and the selected patch series. This file remains historical design context.

# Minimal touchscreen path on 7.3

Status: **designed**, not an enabled or build-validated patch series. Evidence
and grades are in [the session-2 investigation](evidence/2026-10-28-quad-firmware-sequencing.md).
Pen capabilities can be checked after basic touch enumerates.

## First decision: preserve the required bus contract

QCOM0C0E is QUP wrapper 1 / SE2, not the standalone QSPI block. The captured
touch contract selects quad reads and writes with single-lane opcodes. Keep
the 40 MHz/mode-0/CS0 values from ACPI as limits; do not infer alternate
opcodes, a single-lane fallback, or a tested operating frequency.

The next diagnostic boot should use the controller's existing pinctrl only,
with **no HID child, touch-supply consumer or firmware-name addition**. Log
the clocked SE status before protocol dispatch using RFC 0014, then run the
read-only collector. Do not rebind or force a runtime resume from the collector.
The image/kernel owners arrange this controller-only DT variant and build;
this worker does not edit their files. Observe inherited GPIO49/50 settings
before a later image explicitly selects the new mux group.

| Observed state | Next decision |
|:--|:--|
| DT controller disabled / no probe record | State was not sampled. Build the controller-only diagnostic variant; do not call this protocol 0. |
| Protocol 9, plausible revision/hardware/clock fields | Assess the downstream GENI QSPI + GPI path against 7.3. No firmware upload is needed merely to preserve the preloaded personality. |
| Protocol 0, plausible hardware fields | An empty/inactive engine is a hypothesis. Identify a compatible QSPI image and its authorized load path before changing the load predicate. The inspected Fedora image has no protocol 9. |
| All-zero or inaccessible-looking fields | Resolve SE clocks, resets, access and wrapper state with soc-boot. Zero alone does not identify firmware contents. |
| Protocol 1 | Ordinary SPI is programmed. This is not proof it can execute the required quad phases; obtain the personality's transfer contract before using it. |
| Protocol 255 | Generic Linux attempts ordinary SPI loading, but the diagnostic variant must retain the missing firmware-name and avoid a new load. Resolve required personality first. |
| Other nonzero protocol | Keep rejection; investigate the DT/firmware ownership mismatch. |

## Smallest functional implementation

There are four coupled changes, not just a new controller mode_bits value:

1. **GENI host and GPI.** Support the evidenced QSPI personality without
   changing ordinary SPI or target semantics. Validate GPI protocol selection,
   QSPI configuration/GO TRE layouts, command lengths, RX lengths, CS retention,
   direction turnaround, completion channel, cancellation and runtime resume.
   Advertise QUAD only for that supported personality. Fail probe when required
   GPI channels are missing; do not fall back to a one-lane FIFO path. Add dual
   only after its encoding is evidenced, rather than guessing it from quad.
2. **SPI-HID framing.** Prefer forward-porting the posted Romulus
   spi-mem transport/DMA changes onto v7; see the
   [upstream assessment](evidence/2026-10-28-spi-hid-v7.md). Reads
   need opcode TX width 1, address/placeholder TX width 4, data RX width 4;
   writes need opcode TX width 1, address/report TX width 4. Reject unavailable
   required widths before acquiring the touch reset/supply or issuing traffic.
   Preserve trace buffers, DMA-safe allocation, error handling and locking.
   v7 removed the old error-counter sysfs ABI.
3. **Board description.** GPIO40–43 retain SE2 mux1; add GPIO49/50 SE2 mux2.
   Keep GPIO51 as the IRQ. Validate the extra pins' pull/drive translations
   independently; do not transplant their electrical settings from another
   board. Add the correct GENI/GPI compatible and DMA protocol only after their
   binding and host implementation exist. Draft 0012 deliberately does not
   invent them or enable the device.
4. **Protocol and power data.** Apply binding RFC 0015 and RFC 0013, then
   the disabled board draft. MSHW0484 uses eb/e2; v7's G6 default 0b/02
   is not this unit's opcode pair. The regulator supplies the conditional 500 ms
   cold interval; the OF driver supplies 300 ms reset and 10 ms reset-before-
   power-off. Independent verification of all values precedes integration.

Use `spi_mem_op` to describe command, address, dummy and data phases; the
host can implement `spi_controller_mem_ops` for its atomic native QSPI
operation instead of detecting HID opcodes in generic transfers. Validate
`supports_op` and operation lengths, bus widths, SDR/word-size limits and
native GPI completion. Linux's message fallback is useful only once GENI
actually implements those widths and CS retention.

The transport's desired read phases are explicit:

| Transfer | Bytes | Direction / width | CS |
|--:|:--|:--|:--|
| 0 | read opcode `eb` | TX / 1 | retained |
| 1 | three-byte big-endian header/body address | TX / 4 | retained |
| 2 | `ff ff ff ff` placeholders | TX / 4 | retained |
| 3 | input header or body | RX / 4 | released at operation end |

The four placeholder bytes generate eight clocks in quad mode. In dual mode
the equivalent placeholder would be two bytes; in single mode one byte.
The existing five-byte single-SPI approval must not be reused for quad.
An output message similarly splits its opcode from all remaining bytes.
The host must implement the requested phase widths and CS continuity, rather
than infer the HID opcode from the first byte or number of transfers.

The downstream `fullduplex.patch` and GENI patch are **research**, not suitable
unchanged backports: they reinterpret full-duplex SPI as sequential TX/RX,
inspect read opcodes in the host, and choose lane flags from transfer position.
Their 8-clock dummy setting agrees with the HID specification, but that does
not establish the other QSPI microcode/TRE semantics. They also require GPI
changes and assume already programmed protocol 9. The ordinary Linux loader
currently rejects 9, and the inspected firmware contains no matching segment.

This evidence supports a concrete design and the pinmux/sequencing/diagnostic
RFCs. It does **not** yet support an honest working controller patch: the
unit's protocol/revision, the supported GENI QSPI command contract and, if
empty, a compatible firmware source remain unresolved. A patch that just
accepts 0, loads SPI protocol 1 and sets QUAD bits would conceal those gaps.

## Integration gates

The kernel owner can apply the unsigned RFCs in this order for development:
0015 (binding), 0013 (sequencing), 0012 (disabled board), with 0014 separately
for diagnostics. None is in `patches/series`; that file selects the unchanged
11-patch v7 baseline. The old v6 files remain an archive. The worker kernel
checkout still contains the previous session's v6 baseline and old draft.

After the actual host/GPI/transport implementation exists, run
`scripts/kernel-dev.sh` with the touch-pen fragment and both BTF symbols,
check `Image`/modules and their BTF, run `checkpatch --strict`, and validate
all new bindings and the enabled DT. Resolve baseline checkpatch findings
and the unsigned RFCs' missing sign-offs through the human authors; no
Signed-off-by is added by this worker. Do not substitute a minimal-config
compatibility build for the required project dev build. Commission the
Claude cross-check before integration, then collect touch enumeration and
input events on one useful boot. Pen remains optional for this milestone.
