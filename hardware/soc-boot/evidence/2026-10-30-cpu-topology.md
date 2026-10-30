# LCD CPU topology and packaged boot parity

Author: soc-boot, Codex `gpt-6.1-sol`, 2026-10-30. Status: `designed`;
independent Claude cross-check and kernel-owner integration remain open.

## Pinned evidence and grades

**Verified:** `sources/windows/live-inventory/acpi/apic.dat` is catalogued as
structured data, not code (`sources/binary-catalog.tsv:1487`). SHA-256:
`50b032d657ad12b06793d4de71f0425d93a143fbf45965645203b40009a038d0`.
Its existing ACPICA decode, `apic.dsl`, has SHA-256
`5d33cc4ea6086d2e0bbcd64ac4601b3ca03e2449dd32bb3c05fde4312e9dcd92`.
No REA or disassembly was used. This session independently parsed the table
bytes with Python `struct`, checked the APIC signature, length (1049 bytes) and
zero ACPI checksum, and walked all 12 type-11 GICC records. The enabled-bit
results agree with the existing decode:

| UID | MPIDR | Enabled | GICC start | Flags offset | MPIDR offset | Decode lines |
|:--|:--|:--|:--|:--|:--|:--|
| 7 | `0x10300` | 0 | `0x25c` | `0x268` | `0x2a0` | `apic.dsl:188`–`205` |
| 11 | `0x20300` | 0 | `0x39c` | `0x3a8` | `0x3e0` | `apic.dsl:280`–`297` |
| 0–6, 8–10 | remaining ten MPIDRs | 1 | see private local summary | — | — | remaining GICC records |

The UID and flags are little-endian u32 fields at GICC start +8 and +12; MPIDR
is u64 at +68. The local summary is `out/build/soc-boot-parity/madt-summary.json`.
**Inference:** these two firmware-disabled cores are unavailable to the DT
boot. Physical fusing itself is not established by MADT.

**Verified source mapping:** pinned Linux `v7.3`, commit
`c03c1a14507dfaf8b856c2608f9ac216021fc222`:

- `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:161` and `:211` map these
  MPIDRs to `cpu7`/`cpu11`. Their CPU nodes carry SCMI performance IDs 1/2;
  removing the nodes removes those references without removing shared domains.
- `hamoa.dtsi:255` and `:273` reference them from cluster1/cluster2 `core3`.
  `hamoa.dtsi:423` and `:447` define `cpu_pd7`/`cpu_pd11`.
- `hamoa.dtsi:281`, `:292`, `:300`, `:308` define CPU C4, CL4, CL5 and SS3;
  `hamoa.dtsi:473` attaches SS3 to `system_pd`.
- `sources/linux/arch/arm64/boot/dts/qcom/purwa.dtsi:13` demonstrates inherited
  CPU/map/PSCI-node deletion on another X1P SKU.

**Verified configuration / unproven causality:** D20 and
`kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts` already exclude the
system SS3 reference while retaining C4/CL4/CL5. D21/D22 and the operator's M5
evidence report stable GNOME for 234 seconds with GPU off, and reset at session
start with GPU on; both use parity. This supports preserving the tested
configuration, not a claim that SS3 caused resets or is inherently unsafe.
No private M5 raw log lines have been copied here. SS3 safety remains TBD.

## Patch and application

`hardware/soc-boot/patches/0001-arm64-dts-qcom-denali-lcd-boot-parity.patch`
is the next local patch number. It changes only
`arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dts`, adding the same CPU,
map, PSCI and SS3-reference deletions as the parity variant. Its commit message
ends with `Assisted-by: Codex gpt-6.1-sol`; there is no Signed-off-by.

Patch SHA-256:
`ae01a648364c4937c7645d0b3be6266309cf8cfee61cfc6979b8cee662a8e3cb`.

A fresh archive of the pinned commit was extracted into `out/linux/soc-boot`.
All **29** non-comment entries of `kernel/series` were applied in order with
`patch --batch --fuzz=0 -p1`. Their manifest hash was
`1720dd674bc69f90f0a3003645076c7a0d62954d436e34f6fa512e52b6c4b06f`,
matching `kernel/base.toml`. All 28 touched source files matched the existing
M10 source snapshot. Then 0001 applied with **no offsets, fuzz or rejects**:

```bash
patch --batch --fuzz=0 -p1 -d out/linux/soc-boot \
    < hardware/soc-boot/patches/0001-arm64-dts-qcom-denali-lcd-boot-parity.patch
perl sources/linux/scripts/checkpatch.pl --strict --no-signoff \
    hardware/soc-boot/patches/0001-arm64-dts-qcom-denali-lcd-boot-parity.patch
```

Checkpatch: **0 errors, 0 warnings, 0 checks**. This is an append-to-series
patch tested after the full existing series, not a replacement for its S1/GPU
or touch patches. No git-writing command was run; source inputs stayed intact.
If 0001 is the only appended patch, the proposed full-series manifest hash is
`99386516dca7ca35365f4b32905881f31bd85b5960c139a973a2239c8e5dfa49`;
the owner must recompute it if any integration inputs change.

## DT-only verification

Fedora 44 kernel container: GCC `16.2.1-2.fc44`, dtc `1.8.1-6.fc44`,
dt-schema `2026.09-1.fc44`. Only DTS, schema and host-tool build targets ran:

```bash
scripts/kernel-dev.sh --check soc-boot dtbs
scripts/kernel-dev.sh --check soc-boot variant \
    out/build/soc-boot-parity/after-stage/x1p64100-microsoft-denali-m10.dts
scripts/kernel-dev.sh --check soc-boot variant \
    out/build/soc-boot-parity/after-stage/x1p64100-microsoft-denali-m10-notouch.dts
```

Each helper acquired `flock out/.kernel-build.lock` internally. All three
`CHECK_DTBS=y` targets passed with zero diagnostics. Both
`CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y` were checked in
`out/build/dev-soc-boot/.config`; no vmlinux, modules or RPMs were built.

For each of the 15 compiled after-change DTBs, explicit validation used:

```bash
scripts/kernel-container.sh run dt-validate \
    -s out/build/dev-soc-boot/Documentation/devicetree/bindings/processed-schema.json \
    out/build/soc-boot-parity/after/x1p64100-microsoft-denali.dtb
```

The same command with each other DTB path returned zero with empty stdout and
stderr. Kbuild's three DTBs matched standalone `gcc -E` + `dtc -@` output byte
for byte. Effective-status checks with `scripts/kernel-dtb-safety.py` passed
for all 15: the card and both WSA8845 nodes are effectively disabled. The card
and `swr0` also remain explicitly disabled. This patch changes no firmware,
speaker, charger, thermal, GPIO or voltage settings.

Compiled topology checks found ten CPUs, no deleted CPU/PSCI symbols or map
entries, no `system_pd` SS3 reference, all ten CPU C4 references, all three
clusters' CL4/CL5 references, and unchanged SCMI membership of 4 + 3 + 3 CPUs.
Full wiring/S1/GPU/CMA/touch checks used `scripts/kernel-m8-check.py` with
`--variant m10 --cma-dma32` for the packaged/default trees, and
`--variant m10-notouch` for the fallback. This deliberately exercises parity
assertions; its current `--variant packaged` still expects 12 CPUs and needs
the kernel-owner change in R-K1. All properties also compared unchanged to
the archived corresponding M10 DTBs using `--previous-unchanged`. The fallback
has exactly one difference from the default: touchscreen `status = "disabled"`.

## Variant migration and equivalence

**Verified negative case:** after applying 0001, compiling the unchanged M10
source with the old parity include fails: dtc cannot find labels `cpu7`,
`cpu11`, `cpu_pd7`, `cpu_pd11` for a second deletion. Removing a reference
twice is not a safe no-op.

For this test only, all variant sources were copied into a staging directory.
There the parity file was replaced by a simple board include, as specified in
README R-K1. Repository `kernel/**` and `scripts/**` were not edited.

| Inputs compared on the same full-series tree | Before/after result |
|:--|:--|
| parity; m5/m5gpu; m6/m6gpu; m7/m7-touchdiag; m8/m8-notouch; m9/m9-notouch; m10/m10-notouch | All **13 byte-identical** with the staging shim |
| Packaged LCD board | Gains parity; **byte-identical to archived M10 default** |
| eDP-only diagnostic | Gains only the same parity deletions from its board; DP0/DP1 disablement remains |

M7's diagnostic body was generated from the current touch owner's
`hardware/touch-pen/touch-pen-state.dts` with its board include removed, following
the existing builder convention. These old-name comparisons establish no new
differences on the **same current series**; they do not claim historical GPU or
touch behavior when old names are rebuilt on a newer base. Historical source
snapshots/builders and their artifacts remain unchanged. The active M10 pair
also matched the already published local revision-7 DTBs before and after.

Validated SHA-256 values:

| DTB | SHA-256 |
|:--|:--|
| New packaged LCD / M10 default | `4130f2988a593847a0cd490bccd90ee65e16f74a5f3adf019cfd24dda5aec65a` |
| M10 fallback | `5704f68668538f6dd3e6fc37f67e8e9830f771124c57475c0ebca81d8c750519` |

The archived comparison pair is under
`out/dtb-variants/7.3.0-65.sp11.7.fc44.aarch64/qcom/`.

## Local audit artifacts and remaining work

`out/build/soc-boot-parity/` holds `series-manifest.txt`, `series-apply.log`,
`parity-apply.log`, `checkpatch.log`, three `check-dtbs*.log` files,
`comparison.json`, `validation.json`, `*.wiring.json`, before/after DTS/DTBs,
per-DTB S1/schema results, label-preserving diffs and the duplicate-deletion
negative log. Local `verify.py` and `validate.py` record the exact compilation,
comparison and explicit-validation procedure. They can be inspected without
accessing private M5 logs; `verify.py` expects the pre-patch scratch source and
must not be rerun against the already patched source unchanged.

No full kernel build or device reboot was performed. Runtime cpufreq/idle and
three-boot acceptance remain pending, as does the independent cross-runtime
check. R-K1 gives exact kernel-owner integration and release steps; R-I1 batches
read-only device evidence into the next existing collector run.
