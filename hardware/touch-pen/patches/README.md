# Touch/pen patch exports

`series` lists the 11 unchanged **spi-hid v7** patches under `v7/`, in upstream
order. Original decoded bodies and upstream sign-off chains are preserved.
[Latest baseline evidence](../evidence/2026-10-28-spi-hid-v7.md) records hashes,
clean application on 7.3, final source-blob checks and the posted spi-mem quad
transport lead. v7 is not build/schema validated here and still lacks quad.

The root `0001-spi-hid-v6.patch` through `0011-spi-hid-v6.patch` remain as the
historical baseline archive, excluded from current `series`. Their previous
minimal BTF/W=1 results are in the dated v6 evidence, not results for v7.
Do not stack v7 onto v6. The worker kernel checkout is still the previous
session's v6/old DT; it was not changed by this session.

The following are **unsigned, unbuilt RFCs**, excluded from `series`, now
based on v7:

| File | Purpose / order |
|:--|:--|
| `0015-hid-over-spi-mshw0484-binding-rfc.patch` | Apply first: hardware-specific compatible for distinct protocol and timing |
| `0013-spi-hid-mshw0484-sequencing-rfc.patch` | Apply second: eb/e2 match data, 300 ms reset, checked assertion and 10 ms wait before regulator disable |
| `0012-denali-touch-draft.patch` | Apply third: revised disabled DT, GPIO49/50 SE2 mux, v7-compatible binding shape; all devices stay disabled |
| `0014-spi-geni-state-diagnostic-rfc.patch` | Independent temporary probe logging; no HID dependency or firmware-load change |

0012 supersedes the old draft: v7 removes address/opcode properties and the
generic hid-over-spi fallback. Its values now reside in 0013's MSHW0484 match
data. Earlier DT checks do not validate this revision. Extra-pin electrical
settings remain unspecified pending independent cross-check.

The [controller-only diagnostic variant](../touch-pen-state.dts) uses RFC 0014
with the working LCD base, removes wrapper firmware-name, and selects only
stock SPI pins. Verify no enabled HID child or touch-supply consumer. It
requires neither the v7 HID series nor the protocol/sequencing/binding RFCs.

No host quad-support patch is exported. The specific missing microcode/GPI
contract and preferred posted spi-mem transport approach are in
[quad-design.md](../quad-design.md). The old 0027/0028 and downstream
full-duplex/opcode heuristics are not validated substitutes.

Worker-authored commit messages end with `Assisted-by: Codex gpt-6.1-sol`.
No worker Signed-off-by is added. Full strict checkpatch still fails on the
unsigned RFCs; authorship must be resolved by the human owner. The unchanged
v7 series has its own recorded strict findings.
