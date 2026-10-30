# Selected touch/pen patches

`series` is the component order; `../kernel-series.list` contains the exact
repository-relative entries for the kernel worker. Current `kernel/series`
already includes this complete subsequence after speaker/GPU safety;
do not append it again. Diagnostic RFC 0014 was retired for M8.

| Selection | Purpose |
|:--|:--|
| `v7/0001`–`v7/0011` | Jingyuan Liang's posted 2026-10-24 v7 unchanged; preserve original authorship/trailers |
| `0016-dt-bindings-qspi-mshw0484.patch` | QSPI compatible / DMA selector4 / MSHW0484 binding |
| `0017-dmaengine-qcom-gpi-qspi.patch` | Nikkuss/scuggo GPI QSPI TRE path via Dale Whinham's SP11 port |
| `0018-spi-geni-qcom-qspi.patch` | Same provenance, adapted to v7.3 callbacks; preloaded9 only, no firmware upload |
| `0019-spi-hid-mshw0484.patch` | Carter Davis/orvitpng reads, Dale Whinham/Jizhou Tong reset rebind, cross-checked MSHW0484 timing; restricted to this device |
| `0020-denali-lcd-touch.patch` | **Separate** enabled LCD DT node; omit for driver-only builds |

All newly exported commit messages end with `Assisted-by: Codex gpt-6.1-sol`.
No new Signed-off-by was invented. Original author attribution and Link
trailers document the downstream base and posted transport work. Patches
were exported as unified mail-style diffs without git mutations.

Five new patches pass `checkpatch --strict --no-signoff`. The unchanged v7
baseline has six warnings and eleven checks (new-file/MAINTAINERS, short help,
trace formatting), with zero errors under that command. These are recorded,
not suppressed; the whole component remains **designed**. The
[2026-10-30 triage](../evidence/2026-10-30-lint-triage.md) classifies each
finding and replaces the earlier raw lint log, which contained missing-ply
tool errors. All sixteen selected patches are unchanged; no rebuild is
needed for this triage. Upstream exception disposition and independent
QSPI/rebind cross-check remain open.

Root `0001`–`0011` v6, disabled draft `0012`, sequencing RFC `0013` and binding
RFC `0015` are historical and excluded. Diagnostic `0014` is retired from the
integration base. `0019` supersedes `0013`/`0015` behavior.
See working-reference evidence for why generic firmware/protocol0 patches
are not part of the selected fix.
