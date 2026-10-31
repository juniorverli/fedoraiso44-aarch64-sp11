# spectra: Qualcomm Spectra (CPAS 1.0.0, Spectra 695) on Linux v7.3

Stage 1 of the native Spectra port: the kernel side, checked offline. The report is
`../evidence/2026-10-31-spectra-port.md`.

| Path | Content |
|:--|:--|
| `patches/` | `git format-patch` series against Qualcomm's `camera-driver` (`08171dd`, GPL-2.0-only). Two Kbuild patches; original authors untouched, `Assisted-by` trailers, no `Signed-off-by` |
| `scripts/prep-tree.sh` | Composes the scratch kernel tree (`out/linux/spectra` = v7.3 + `kernel/series`), the `.config` like `kernel/config`, the driver clone with the patches, and the stand-in symbol list for modpost |
| `scripts/build-spectra.sh` | `make M=... CAMERA_ARCH=x1e80100 modules` in the Fedora 44 container, under the kernel build lock; modes `build`, `plain`, `obj` |
| `scripts/check-downstream-dt.sh` | Compiles Qualcomm's downstream hamoa camera DT (`out/ref/qcl-hamoa-camx-dts`) on top of the Denali DTS and reports every label our tree lacks |
| `scripts/extra-blocks.mk` | Optional extra mk to try the blocks `CONFIG_X1E80100` does not enable (FD, LRME, CRE, OPE, TFE, custom) |

Nothing here is committed to a kernel tree and nothing was run on the device. The downstream driver and the
Qualcomm prebuilt userspace live in `out/ref/` (never in git).
