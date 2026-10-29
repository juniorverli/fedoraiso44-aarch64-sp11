# M9 Wi-Fi candidate validation

## Scope

Project edits are confined to `hardware/wifi/`; all changes remain
uncommitted (D24, operator instruction). No git command that writes was used.
The local `out/linux/wifi` build tree started with v7.3 plus Wi-Fi 0001;
it now contains the current `kernel/series` prerequisites and Wi-Fi 0002/0003
as uncommitted test-tree changes. Use the numbered Wi-Fi patch files for
integration, not a blanket diff of this build tree. Shared `sources/` was
not edited. No device was rebooted or accessed by this worker.

## Completed checks

- Both new patches apply cleanly to the integrated M8 kernel tree using
  `git apply --check` (read-only). Patch 0002's code diff is identical to
  the retrieved upstream patch, excluding mail metadata, index hashes and
  hunk offsets.
- `sources/linux/scripts/checkpatch.pl --strict --no-signoff` on 0002 and
  0003: **0 errors, 0 warnings, 0 checks**. `--no-signoff` is the explicit
  repository exception: no Signed-off-by is added. Both proposed commit
  messages end with `Assisted-by: Codex gpt-6.1-sol`.
- `scripts/kernel-dev.sh --check wifi dtbs`: **pass**, 47 s. DTB builds and
  dt-schema validates without warnings/errors. Log:
  `out/build/dev-wifi-m9-dtbs.log`, SHA-256
  `c23955a6785343fe76ea841552db74caf7dd81fb4edc0d4e95e328e233986a6b`.
  `fdtget -tx ... /reserved-memory/linux,cma alloc-ranges` returns
  `0 80000000 0 80000000`.
- `scripts/kernel-dev.sh --check wifi variant kernel/dtb-variants/x1p64100-microsoft-denali-m8.dts`: **pass**, 12 s, no warnings/errors.
  Log: `out/build/dev-wifi-m9-m8-variant.log`. The inherited CMA range is
  correct in this boot variant; `/sound`, `soundwire@6b10000` and
  `gpu@3d00000` remain disabled.
- `scripts/kernel-dev.sh wifi module drivers/net/wireless/ath/ath12k`:
  **pass**, 695 s, no warnings/errors. Log:
  `out/build/dev-wifi-m9-ath12k.log`. Built the BTF-enabled `vmlinux`, then
  compiled the complete ath12k directory including patched `core.o`,
  `ath12k.o` and `wifi7/ath12k_wifi7.o`.
- Build `.config` retains `CONFIG_DEBUG_INFO_BTF=y`,
  `CONFIG_DEBUG_INFO_BTF_MODULES=y`, `CONFIG_ATH12K_DEBUG=y`; Fedora
  `readelf -SW` confirms `.BTF` and `.BTF_ids` in `vmlinux`.
- Both builds used the Fedora 44 container and the helper's shared
  `out/.kernel-build.lock`. The first attempt on the old Wi-Fi tree stopped
  at the config guard because M8 SPI-HID symbols were absent; applying the
  existing integration prerequisites locally resolved that configuration
  mismatch. The successful build uses the current unmodified fragments.
- Board-file builder: independent rebuilds are byte-identical, output
  SHA-256 `74d0f9f9f6a601265367698a97bc58a5e7c6e28fe1c323c815feb3d5e3026891`.
  Parsed output has exactly one prepended Windows override and every
  original Fedora IE/sub-element unchanged, including REGDB. Re-encoding
  the input and output preserves structure and length. Negative checks
  reject malformed/truncated TLVs, a mismatched Windows hash and an output
  path outside `out/`. No Windows bytes are stored in the test evidence.
- `bash -n` passes on `collector/wifi.sh` and `tools/check-mac.sh`.
  The local MAC checker now runs; M8 reports DIFFERENT/type 3, so this is
  not a permanent-OTP result.
- `scripts/index.py --check`: **21 components, 0 errors**.
  Project `git diff --check` is clean. A literal-address scan of Wi-Fi
  deliverables finds no MAC/BD addresses.

## Limits and hand-back

The helper's directory target checks driver object compilation; this worker
has not produced or linked a complete set of release `.ko` files/RPMs. K3
requires the kernel owner's integrated RPM/module build with BTF. These
artifacts must not be presented as a tested M9 ISO.

Status remains `designed`: independent cross-check (especially the new CMA
window), source pinning, image integration and this unit's M9 runtime
results remain open. Required outputs are in README Requests K3/K4, F2,
I1–I8, SRC1 and O1/O2. The next step is one private M9 boot, retaining a
session-active read-only Wi-Fi snapshot as specified in `test-plan.md`.
