# spi-hid v7 strict-lint triage

Status: **designed**. All six warnings and eleven checks belong to the
unchanged exported upstream v7 series. Our patches 0016–0020 each report
zero errors, warnings and checks. No kernel patch was changed, so this
triage requires **no rebuild**. The orchestrator still needs to decide the
upstream lint exception and commission the independent QSPI/TRE/rebind
cross-check; this document does not grant sw-ready or device clearance.

## Inputs and method

Verified software results, 2026-10-30:

- Pinned v7.3 commit: `c03c1a14507dfaf8b856c2608f9ac216021fc222`;
  confirmed against `v7.3^{commit}`, then exported with read-only `git archive`.
- Project HEAD: `c0488eaeac01d13cdff16c24fcce5a7facbc40e2`.
- Current `kernel/series`: **29 patches**, including the sixteen selected
  touch patches exactly once; RFC 0014 is retired. The kernel helper's
  canonical series digest is
  `1720dd674bc69f90f0a3003645076c7a0d62954d436e34f6fa512e52b6c4b06f`.
- Disposable composed source: `out/linux/touch-pen-lint-20261030/`.
  Output/log directory: `out/agents/touch-pen/lint-20261030/`.
- All eleven v7 files and 0016–0020 match project HEAD byte-for-byte;
  all 29 patch hashes also remain equal to the initial input manifest.
  The upstream bodies, authorship and existing trailers were preserved.
- Fedora 44 kernel image:
  `sha256:e16f942e4b77122a11f38dc3aec8d3f3b6a3df38221272d09a58bdf9ab24408c`;
  Python 3.14.8, dt-schema 2026.09, Fedora `python3-ply-3.11-33.fc44.noarch`.

The existing image lacks `ply`. The older raw file
`out/agents/touch-ref/checkpatch-final.txt` contains SPDX-helper
`ModuleNotFoundError: No module named 'ply'` tracebacks, contrary to the
2026-10-29 validation note's claim that the final run had no tool error.
This session replaces that lint evidence with a fresh complete run. Fedora's
RPM was downloaded and extracted only under the disposable output directory,
then supplied through `PYTHONPATH`; no host package or shared container image
was changed. RPM SHA-256:
`5d311ca7cd31f405096a1a8a38fa0743c4681f6091552da0922ac53c80d265a1`.
The new raw output has no tool stderr or tracebacks.

The component helper now supports `--kernel-root`/`--output`, includes
checkpatch diagnostic type names, and fails on tool stderr or missing totals
instead of accepting an incomplete SPDX check. Reproduce the lint after
composing the tree below:

```sh
triage_out="$PWD/out/agents/touch-pen/lint-20261030"
mkdir -p "$triage_out/deps"
scripts/kernel-container.sh run dnf \
    --setopt=cachedir=/tmp/touch-pen-dnf-cache \
    --setopt=persistdir=/tmp/touch-pen-dnf-state \
    download --destdir="$triage_out/deps" python3-ply
scripts/kernel-container.sh run bash -e -o pipefail -c '
    cd "$1"
    rpm2cpio python3-ply-3.11-33.fc44.noarch.rpm | cpio -idm --quiet
' bash "$triage_out/deps"
scripts/kernel-container.sh run env \
    PYTHONPATH="$triage_out/deps/usr/lib/python3.14/site-packages" \
    python3 -B hardware/touch-pen/tools/check-patches.py \
    --kernel-root out/linux/touch-pen-lint-20261030 \
    --output "$triage_out"
```

For every entry in `patches/series`, the helper feeds the **patch content on
stdin** to the pinned tree's checker, with the composed tree as its cwd:

```sh
scripts/checkpatch.pl --strict --no-signoff --show-types --root="$triage_tree" - < "$patch_path"
```

`--no-signoff` follows the other workers' invocation and the operator's
no-invented-signoff policy. All style checks remain enabled, without
`--ignore`, `--fix` or patch-path source-file autodetection. The command
returns **1**, correctly retaining the upstream findings; it is not a clean
whole-series result.

## Results by patch

Names are relative to `hardware/touch-pen/patches/`. E/W/C are checkpatch's
errors, warnings and strict checks.

| Patch | E | W | C | Classification / action |
|:--|--:|--:|--:|:--|
| v7/0001 | 0 | 0 | 0 | Upstream; preserve |
| v7/0002 | 0 | 0 | 0 | Upstream; preserve |
| v7/0003 | 0 | 2 | 0 | Upstream reminders/help omission; preserve, triaged below |
| v7/0004 | 0 | 0 | 0 | Upstream; preserve |
| v7/0005 | 0 | 0 | 0 | Upstream; preserve |
| v7/0006 | 0 | 1 | 11 | Upstream reminder/trace conventions; preserve, triaged below |
| v7/0007 | 0 | 1 | 0 | Upstream reminder; preserve |
| v7/0008 | 0 | 1 | 0 | Upstream reminder; preserve |
| v7/0009 | 0 | 1 | 0 | Upstream reminder; preserve |
| v7/0010 | 0 | 0 | 0 | Upstream; preserve |
| v7/0011 | 0 | 0 | 0 | Upstream; preserve |
| 0016-dt-bindings-qspi-mshw0484.patch | 0 | 0 | 0 | Ours; no fix required |
| 0017-dmaengine-qcom-gpi-qspi.patch | 0 | 0 | 0 | Ours; no fix required |
| 0018-spi-geni-qcom-qspi.patch | 0 | 0 | 0 | Ours; no fix required |
| 0019-spi-hid-mshw0484.patch | 0 | 0 | 0 | Ours; no fix required |
| 0020-denali-lcd-touch.patch | 0 | 0 | 0 | Ours; no fix required |
| **Total** | **0** | **6** | **11** | **All 17 findings upstream; zero ours** |

## Every finding and its disposition

`#N` is the patch-input line printed by checkpatch, not a line of a private
device log. Source line numbers below are those printed by checkpatch and
remain present in the composed tree. Every row is classified **upstream,
keep unchanged** under this assignment.

| ID | v7 patch / input line | Diagnostic | Location / reason to retain |
|:--|:--|:--|:--|
| W1 | 0003 / #50 | FILE_PATH_CHANGES | New Kconfig/Makefile/core files trigger the MAINTAINERS reminder; upstream file introduction, not a local patch regression |
| W2 | 0003 / #60 | CONFIG_DESCRIPTION | `drivers/hid/spi-hid/Kconfig:6`, top-level `menuconfig SPI_HID` lacks help; a real upstream documentation omission, retained rather than rewriting the export |
| W3 | 0006 / #271 | FILE_PATH_CHANGES | New core/trace headers trigger the same upstream MAINTAINERS reminder |
| C1 | 0006 / #408 | PARENTHESIS_ALIGNMENT | `spi-hid-trace.h:24`, indented `TP_PROTO` in `spi_hid_transfer`; trace convention A below |
| C2 | 0006 / #413 | OPEN_ENDED_LINE | `spi-hid-trace.h:29`, `TP_STRUCT__entry(`; trace convention B below |
| C3 | 0006 / #425 | OPEN_ENDED_LINE | `spi-hid-trace.h:41`, `TP_fast_assign(`; trace convention B |
| C4 | 0006 / #462 | PARENTHESIS_ALIGNMENT | `spi-hid-trace.h:78`, indented `TP_PROTO` in `spi_hid_irq`; trace convention A |
| C5 | 0006 / #466 | OPEN_ENDED_LINE | `spi-hid-trace.h:82`, `TP_STRUCT__entry(`; trace convention B |
| C6 | 0006 / #472 | OPEN_ENDED_LINE | `spi-hid-trace.h:88`, `TP_fast_assign(`; trace convention B |
| C7 | 0006 / #486 | PARENTHESIS_ALIGNMENT | `spi-hid-trace.h:102`, indented `TP_PROTO` in `spi_hid`; trace convention A |
| C8 | 0006 / #490 | OPEN_ENDED_LINE | `spi-hid-trace.h:106`, `TP_STRUCT__entry(`; trace convention B |
| C9 | 0006 / #505 | OPEN_ENDED_LINE | `spi-hid-trace.h:121`, `TP_fast_assign(`; trace convention B |
| C10 | 0006 / #567 | SPACING | `spi-hid-trace.h:183`, first hyphen in `TRACE_INCLUDE_FILE spi-hid-trace`; filename token, reason C below |
| C11 | 0006 / #567 | SPACING | Same line, second hyphen; a separate reported check with the same filename requirement |
| W4 | 0007 / #59 | FILE_PATH_CHANGES | New ACPI frontend files; upstream MAINTAINERS reminder |
| W5 | 0008 / #22 | FILE_PATH_CHANGES | New `Documentation/devicetree/bindings/input/hid-over-spi.yaml`; upstream MAINTAINERS reminder |
| W6 | 0009 / #54 | FILE_PATH_CHANGES | New OF frontend file; upstream MAINTAINERS reminder |

Reasons, checked against the pinned v7.3 source:

- **A — trace macro indentation:** the one-tab `TP_PROTO` indentation is
  also used in `sources/linux/include/trace/events/spi.h:11` and the tracing
  sample at `sources/linux/samples/trace_events/trace-events-sample.h:516`.
  Checkpatch's generic function-call alignment rule flags an existing trace
  macro convention. Preserve the upstream formatting.
- **B — trace macro blocks:** the same sample opens `TP_STRUCT__entry(` at
  `sources/linux/samples/trace_events/trace-events-sample.h:522` and
  `TP_fast_assign(` at `:527` on their own lines. Multiline field/assignment
  blocks are expected trace syntax/style, not a local unfinished expression.
- **C — include filename:** `sources/linux/include/trace/define_trace.h:9`
  documents that `TRACE_INCLUDE_FILE` names the header without `.h`;
  `:110` stringifies the path and `:118` includes it. Here the required header
  is `spi-hid-trace.h`. Adding operator whitespace would alter the stringified
  filename. Keep both hyphens unchanged.
- **MAINTAINERS reminders:** checkpatch emits a generic new-file reminder
  (`sources/linux/scripts/checkpatch.pl:3492`), not proof of an unowned file.
  The new driver files fall under the existing HID core `drivers/hid/`
  coverage at `sources/linux/MAINTAINERS:11598`. Preserve the upstream series;
  the binding reminder and any more specific ownership entry remain upstream
  review items. Do not invent a maintainer assignment or modify another
  owner's files to silence these warnings.
- **Kconfig omission:** unlike the trace conventions, W2 is an actual
  missing-help issue. Later v7 patches add frontend help but leave this
  top-level menu unchanged. This is explicitly retained upstream debt,
  requiring the same orchestrator disposition as the other baseline findings.

No local 0016–0020 change introduced a finding, and no local change is needed
to fix these upstream locations. Their export and existing patch contexts
were deliberately preserved; no warning-suppression follow-up patch was added.

## Full current-series application

On the fresh full v7.3 export, **all 29 patches pass `git apply --check`**
sequentially. After each read-only check, GNU `patch --batch --fuzz=0` updates
only the disposable source for the next dependency. No git apply mutation,
index update, checkout, worktree creation, rebase or commit was run.

Core reproducer, with a previously unused `triage_tree` directory:

```sh
triage_tree="$PWD/out/linux/touch-pen-lint-20261030"
mkdir -p "$triage_tree"
git -C sources/linux archive c03c1a14507dfaf8b856c2608f9ac216021fc222 |
    tar -xf - -C "$triage_tree"
while IFS= read -r patch_path; do
    patch_path=${patch_path%%#*}
    [[ -n ${patch_path//[[:space:]]/} ]] || continue
    GIT_CEILING_DIRECTORIES="$(realpath "$triage_tree/..")" \
        git -C "$triage_tree" apply --check "$PWD/$patch_path" || exit
    patch --batch --fuzz=0 --no-backup-if-mismatch -d "$triage_tree" \
        -p1 -i "$PWD/$patch_path" || exit
done < kernel/series
```

There are no rejected hunks or fuzz. Expected offsets match the current
integration: Wi-Fi 0001 has two -2 offsets, USB-C 0001 one +4 offset,
touch 0018 six -8 offsets from retired diagnostic 0014, and touch 0020 two
+4 offsets from the GPU-disable override. All other hunks, including all
v7 hunks, apply without offsets. No patch was rebased just to remove offsets.

Raw application output: `series-apply.log`; per-patch return codes/offsets:
`series-apply.json`; initial hashes/base: `inputs.json`; final unchanged
comparison: `patch-integrity.txt`, all under the output directory above.

## Touch DT and binding validation

The DT-only build uses exactly the freshly composed 29-patch tree. The normal
helper takes `flock out/.kernel-build.lock`, runs Fedora's tools, retains the
disk guard and keeps both BTF symbols enabled. It builds no Image, vmlinux or
kernel modules in this session.

```sh
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
    scripts/kernel-dev.sh --check touch-pen-lint-20261030 dtbs

triage_obj="$PWD/out/build/dev-touch-pen-lint-20261030"
triage_dtb="$triage_obj/arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dtb"
scripts/kernel-container.sh run dt-validate \
    -s "$triage_obj/Documentation/devicetree/bindings/processed-schema.json" \
    "$triage_dtb"
scripts/kernel-container.sh run dt-doc-validate \
    "$triage_tree/Documentation/devicetree/bindings/spi/qcom,spi-geni-qcom.yaml" \
    "$triage_tree/Documentation/devicetree/bindings/input/hid-over-spi.yaml"
scripts/kernel-container.sh run python3 -B scripts/kernel-m8-check.py \
    "$triage_dtb" --variant packaged --cma-dma32
```

Results:

- `CHECK_DTBS=y`: **exit 0**, target **43 s**, command including setup/lock
  handling **55.399 s**, 32 MiB output. No DTC/schema warnings or errors.
- Explicit `dt-validate`: **exit 0, zero diagnostic bytes**, with the full
  generated schema and no schema filter or warning suppression.
- Both changed bindings: `dt-doc-validate` **exit 0, zero diagnostic bytes**.
- The existing compiled-DTB safety and wiring checkers pass: sound card,
  soundwire speaker bus and GPU disabled; QSPI/MSHW0484 enabled with selector4,
  four lanes, expected IRQ/reset/supply/timing, and no touch firmware request.
  The current integration's CMA window also passes. These reproduce existing
  board expectations; no new hardware value is inferred from schema success.
- `CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y` remain in
  the development config. No new BTF kernel-build claim is made.
- DTB SHA-256:
  `784de3eb644bc6a169cbe0c6da51cef0f984984493a44e6fbfd00b18cd792709`,
  equal to the kernel worker's recorded M10 packaged LCD DTB.

Outputs: `check-dtbs.{log,json}`, `dt-validate.log`, `dt-doc-validate.log`,
`effective.dts`, `dtb-safety.json`, `dtb-wiring.json` under the output directory.

## Hand-back and remaining gates

- **Status:** designed; all lint findings classified, not silently waived.
  `component.toml` and dossier Log updated. `scripts/index.py --check`:
  21 components, zero errors; tracked whitespace and helper syntax checks pass.
- **Findings:** all 17 findings originate in upstream v7; our five patches
  remain clean and unchanged; the exact current full series applies and its
  enabled touch DT validates without diagnostics.
- **Kernel request:** no patch used by `kernel/series` changed, so no rebuild
  is needed for this work. Add Fedora `python3-ply` to the build container
  dependencies to avoid incomplete checkpatch SPDX checks in future runs.
- **Orchestrator request / next:** decide the documented upstream exception
  and obtain the pending independent Claude QSPI register/TRE/rebind
  cross-check. Board GPIO/timing cross-check evidence remains unchanged.
  Review/commit these uncommitted worker files under D24. No device test was
  requested or performed; device acceptance remains pending.

Audit SHA-256 values:

| Output under out/agents/touch-pen/lint-20261030 | SHA-256 |
|:--|:--|
| inputs.json | `3cb39d27cfed42b48c474df9a66dcda731bc22683f39fdc822c6a1380af26b13` |
| checkpatch.log | `fa5ffadb5150212bca0aba32ce5340a5fcde18d8802bee592e990399edad4022` |
| series-apply.json | `3eaac0c57808317260ed8dde2dd48a61b99088736d97cb06b85b37f2852c4fd0` |
