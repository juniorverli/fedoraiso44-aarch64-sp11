# Session 3 software validation

2026-10-30 correction: the older raw `checkpatch-final.txt` contains
missing-`ply` SPDX-helper tracebacks despite the claim below. Use the
[fresh lint triage](2026-10-30-lint-triage.md) for complete lint evidence and
current 29-patch application/DT checks. This is a historical session-3
record: its `verify-series.py` command predates integration and appends the
component series, so do not run it against today's already-integrated
`kernel/series`.

Status **designed**. No device test, firmware upload, shared-owner edit or
write-capable git command was performed. Five new working-reference port
patches are selected after the unchanged v7 baseline; DT enablement is separate.

## Inputs and application

- Base: pinned Linux v7.3,
  `c03c1a14507dfaf8b856c2608f9ac216021fc222`.
- Base integration: current `kernel/series` (nine patches): display-lcd
  0001–0003, wifi 0001, usb-typec 0001, ec-sam 0001/0003, touch diagnostic
  0014 and S1 speaker disablement. The existing wifi patch has line offsets
  in the base composition; no owner patch was edited.
- Component: eleven unchanged spi-hid v7 messages, then 0016–0020 from
  `patches/series` (16 patches). No v6 or disabled/sequencing/binding RFC
  is included. Diagnostic 0014 is already in the base, not duplicated.
- The old uncommitted worker kernel edits were archived before restoring
  their known source files from pinned v7.3. Archive:
  `out/agents/touch-ref/kernel-session2.tar.gz`. No git reset/checkout/index
  operation was used. All work stayed in the task-authorized worker tree
  `out/linux/touch-pen`; the immutable source tree was not changed.

Reproducer:

```sh
python3 -B hardware/touch-pen/tools/verify-series.py
```

Result: **25 total patches apply; all 16 component patches have zero fuzz and
zero offsets; all 24 touched final source files match the actual worker tree
byte-for-byte.** Sparse application log and SHA-256 manifest:
`out/agents/touch-ref/{series-apply.log,series.sha256}`.

## BTF builds

All builds use `scripts/kernel-dev.sh`, which takes
`flock out/.kernel-build.lock`, the Fedora 44 build container, ccache, the
normal project/development fragments and this component's additional fragment.
No build ran concurrently with another kernel build. Toolchain: Fedora 44,
GCC 16.2.1, pahole 1.32 and dt-schema 2026.09. Container image ID:
`sha256:e16f942e4b77122a11f38dc3aec8d3f3b6a3df38221272d09a58bdf9ab24408c`.

```sh
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
    scripts/kernel-dev.sh --check touch-pen dtbs
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
    scripts/kernel-dev.sh touch-pen module drivers/hid/spi-hid
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
    scripts/kernel-dev.sh touch-pen all
```

- DT helper completed in **45 s**, including `CHECK_DTBS=y`.
- Initial HID helper completed in **593 s**: built a BTF vmlinux and the
  SPI-HID core/OF/ACPI objects. The helper's directory target does not link
  final `.ko` files; that result alone is not counted as module completion.
- The final `all` build uses the additional HIDRAW/UINPUT settings and is
  recorded below after completion. It builds Image, DTBs and modules so
  final module linkage and module BTF are actually exercised.

Build output is outside git in `out/agents/touch-ref/dev-{dtbs,hid,all}.log`.
Final `all` build: **exit 0, 1001 s**, 7.7 GiB output directory. There are
no compiler warnings/errors, modpost errors or skipped module BTF messages.
Both BTF configuration symbols remain enabled; HIDRAW=y and UINPUT=m also
survive the final configuration. `readelf -SW` confirms `.BTF` in vmlinux,
`gpi.ko`, `spi-geni-qcom.ko`, `spi-hid.ko`, `spi-hid-of.ko` and
`spi-hid-acpi.ko`. `modinfo -F alias spi-hid-of.ko` includes both
`spi:mshw0484` and the MSHW0484 OF aliases. These are development artifacts,
not release RPMs or a device result.

Final artifact record: `out/agents/touch-ref/artifacts.json`. Configuration
SHA-256: `2d089a1757845c418538a33b39cefe5a52d06de0473feb80f9411bf5a90def1b`.

The updated controller-only variant also passes:

```sh
SP11_DEV_FRAGMENT="$PWD/hardware/touch-pen/kernel-dev.config" \
    scripts/kernel-dev.sh --check touch-pen variant hardware/touch-pen/touch-pen-state.dts
```

Result: **exit 0, 15 s**, no DTC/schema diagnostics. Direct compiled-DTB
inspection confirms it removes the touchscreen child and its supply, uses
generic SPI/GPI selector1, selects only the original two pin groups, has no
firmware-name and keeps both speaker paths disabled. It deliberately does
not enable the extra pins or send touch traffic; rejecting protocol9 in the
generic driver is expected after the state sample. The image owner must
combine this with its GPU-off device-entry policy. Variant log and inspection:
`out/agents/touch-ref/{dev-state-dtb.log,state-dtb-inspection.txt}`.

## DT schema validation

Both changed bindings and the final enabled LCD DT validate without output:

```sh
scripts/kernel-container.sh run dt-validate \
    -s "$PWD/out/build/dev-touch-pen/Documentation/devicetree/bindings/processed-schema.json" \
    "$PWD/out/build/dev-touch-pen/arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dtb"
scripts/kernel-container.sh run dt-doc-validate \
    "$PWD/out/linux/touch-pen/Documentation/devicetree/bindings/spi/qcom,spi-geni-qcom.yaml" \
    "$PWD/out/linux/touch-pen/Documentation/devicetree/bindings/input/hid-over-spi.yaml"
```

Exit status 0 for each; `dt-validate.txt` and `dt-doc-validate.txt` under the
research output directory are empty. No schema filters, ignored properties
or warning suppression were used. Direct `fdtget` inspection of the compiled
LCD DTB also confirms `/sound` and `swr0` disabled, QSPI/MSHW0484 enabled,
four-lane properties present and no firmware-name on SE2 or QUP1. The
inspection result is in `out/agents/touch-ref/dtb-inspection.txt`.

## Strict checkpatch

Exact selected-series checker (inside Fedora to provide SPDX dependencies):

```sh
scripts/kernel-container.sh run \
    python3 -B hardware/touch-pen/tools/check-patches.py
```

It feeds patch content on stdin to `scripts/checkpatch.pl --strict --no-signoff`
with the composed kernel root. This matters: checkpatch treats a **tracked
patch path** as a source file when run from the project git checkout. An
initial path-based invocation therefore checked patch-envelope whitespace,
not the kernel diff. Those results were discarded and replaced by this
correct stdin-based invocation. An initial host invocation also lacked Python
`ply`; the final Fedora invocation has no such tool error.

| Selected patch group | Errors | Warnings | Checks | Result |
|:--|--:|--:|--:|:--|
| 0016–0020, each | 0 | 0 | 0 | Clean |
| Unchanged v7 01/02/04/05/10/11 | 0 | 0 | 0 | Clean |
| Unchanged v7 03 | 0 | 2 | 0 | New-file/MAINTAINERS reminder and short Kconfig help |
| Unchanged v7 06 | 0 | 1 | 11 | New-file reminder and trace macro/include-name style |
| Unchanged v7 07/08/09, each | 0 | 1 | 0 | New-file/MAINTAINERS reminder |
| **Whole component series** | **0** | **6** | **11** | **Not clean; five patches return findings** |

Raw final output: `out/agents/touch-ref/checkpatch-final.txt`. The original
upstream bodies, authorship and existing Signed-off-by trailers are retained;
no sign-off was invented and no finding was suppressed. Clear/triage this
baseline gate with the orchestrator before promoting status. The new patches
split bindings from implementation and use `fsleep(10000)` for the reference's
10 ms settle, avoiding the short-msleep warning without shortening the delay.

## Other checks and remaining gates

- `bash -n hardware/touch-pen/collect-read-only.sh`: pass.
- All three embedded collector Python blocks and both verification helpers
  parse with `ast.parse`; no bytecode is generated.
- `python3 -B scripts/index.py --check`: **21 components, 0 errors**.
- `git --no-optional-locks diff --check`: pass for tracked changes.
- Collector was not executed on the development host or on the operator's PC.
- Board GPIO/timing values match the merged Claude cross-check. New downstream
  QSPI register/TRE constants and the v7 heatmap-rebind port still require
  independent Claude review/cross-check under protocol §5.1.
- Actual protocol9, input capabilities, metadata-derived iptsd configuration
  and touch/pen behavior remain device evidence, not software-build results.

The successful final BTF build does not clear the recorded full-series
strict lint and independent-cross-check gates. Status remains **designed**.

## Final artifact hashes

| Artifact under out/build/dev-touch-pen | SHA-256 |
|:--|:--|
| `vmlinux` | `7ffebeb4c4d596bbbaf9c06397cc09a48063d10c2a70e74f4e769d6f939def14` |
| `drivers/dma/qcom/gpi.ko` | `b2f2287b99cf5da34cdc4582d5e51a2ae3161e0f670598e20ee1eb808474e85e` |
| `drivers/spi/spi-geni-qcom.ko` | `b1c5750191d1088175d6eb2f0e52ec187c82e949e8ae7057ba0270a3a300927f` |
| `drivers/hid/spi-hid/spi-hid.ko` | `e626be9ea083314a3171552eb7b23a6244f5d3eb0d00e5f4d41eb2d24463a5f6` |
| `drivers/hid/spi-hid/spi-hid-of.ko` | `bbb05762cbc2878de4559174f9ac3f5834c527a7b587f3d31155100c8f58973b` |
| `drivers/hid/spi-hid/spi-hid-acpi.ko` | `03c70e4abffa50001200c484b7f54cdc2b12cd5583c3bab398f7968be56b54a1` |
| `arch/arm64/boot/Image` | `f214c452f892ce55a7683f5af2dc23d6227386bdc4baccba57ce16a465a4ab04` |
| `arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dtb` | `766c29670626570a8d446434ee33b33ff8a456052cd0fc0046f7681e9c6f007e` |

## New patch hashes

| Patch under hardware/touch-pen/patches | SHA-256 |
|:--|:--|
| `0016-dt-bindings-qspi-mshw0484.patch` | `c0d44b0d652cc2f5c9b2d6242d0d81ec581aaf4fd6858ab65ecc38a5b1a19a0b` |
| `0017-dmaengine-qcom-gpi-qspi.patch` | `be0d6cb6d4b4a5670a8579bc6077009b6572b40fd39e6b3ecd344c4a58d5ed3c` |
| `0018-spi-geni-qcom-qspi.patch` | `665ab1305d558c154a28a73cbfcf67483988c4a0159a5e6b082c2cb7880c43e2` |
| `0019-spi-hid-mshw0484.patch` | `83ceebe15f0a6a37f8b97f101aa05e4ca62229b254a8be73a41a64058e3a0eab` |
| `0020-denali-lcd-touch.patch` | `ce46507907670c125fe623b233cef8120ec3948d3ff4c630d52bbd20f6fa8039` |
