#!/usr/bin/env bash
# Build the diagnostic DTB variants next to the RPM kernel (DT-only, seconds, no RPM).
#
#   scripts/kernel-dtb-variants.sh [KVER]
#
# KVER defaults to the version of the RPMs this repo builds (kernel/base.toml: tag, spec release, series_rev),
# e.g. 7.3.0-65.sp11.3.fc44.aarch64. The variants are DT-only: rebuilt, never patched in the RPM.
# Output: out/dtb-variants/<kver>/qcom/<name>.dtb and <name>.json (source commit, patches, sha256).
#   x1p64100-microsoft-denali-nobl      display-lcd 0001+0002 (no backlight node)       tree out/linux/m3nobl
#   x1p64100-microsoft-denali-edponly   0001-0003, mdss_dp0/dp1 disabled (H5), from
#                                       kernel/dtb-variants/<name>.dts                  tree out/linux/m3
# The trees are kernel worktrees (branches w/m3nobl = v7.3 + series[0:2], w/m3 = v7.3 + series).
# Owner: kernel worker.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"
kver="${1:-$KERNEL_KVER}"
base_dtb=$(kernel_toml dtb); outdir="$SP11_OUT/dtb-variants/$kver/qcom"
mkdir -p "$outdir"

build() {   # name tree-id patches-description overlay-or-empty
  local name=$1 id=$2 patches=$3 overlay=$4 src="$SP11_OUT/linux/$2" built dtbfile sum
  if [[ -n $overlay ]]; then
    "$KERNEL_REPO/scripts/kernel-dev.sh" "$id" variant "$overlay"
    built="$SP11_OUT/build/dev-$id/arch/arm64/boot/dts/qcom/$name.dtb"
  else
    "$KERNEL_REPO/scripts/kernel-dev.sh" "$id" dtbs
    built="$SP11_OUT/build/dev-$id/arch/arm64/boot/dts/$base_dtb"
  fi
  cp -f "$built" "$outdir/$name.dtb"
  sum=$(sha256sum "$outdir/$name.dtb" | cut -d' ' -f1)
  SERIES_REV=$KERNEL_SERIES_REV python3 -I - "$outdir/$name.json" "$name" "$kver" "$id" "$(git -C "$src" rev-parse HEAD)" "$patches" \
      "${overlay:+$(sha256sum "$overlay" | cut -d' ' -f1)}" "${overlay:+${overlay#$KERNEL_REPO/}}" "$sum" \
      "$(git -C "$src" log --reverse --format=%s v7.3..HEAD | paste -sd'|')" <<'PY'
import json, os, sys
out, name, kver, tree, commit, patches, ovsha, ovpath, sha, subjects = sys.argv[1:11]
json.dump({"name": name, "kver": kver, "base": "v7.3 c03c1a14507dfaf8b856c2608f9ac216021fc222",
           "series_rev": int(os.environ["SERIES_REV"]), "kernel_tree": f"out/linux/{tree}", "source_commit": commit,
           "patches_applied": patches.split(","), "patch_subjects": subjects.split("|"),
           "overlay": ovpath or None, "overlay_sha256": ovsha or None,
           "dtb": f"qcom/{name}.dtb", "sha256": sha}, open(out, "w"), indent=2)
open(out, "a").write("\n")
PY
  echo "kernel-dtb-variants: $outdir/$name.dtb sha256 $sum"
}

P1=hardware/display-lcd/patches/0001-drm-panel-edp-add-LGD-077b.patch
P2=hardware/display-lcd/patches/0002-arm64-dts-qcom-denali-mux-edp-hpd.patch
P3=hardware/display-lcd/patches/0003-arm64-dts-qcom-denali-lcd-backlight.patch
build x1p64100-microsoft-denali-nobl    m3nobl "$P1,$P2"       ""
build x1p64100-microsoft-denali-edponly m3     "$P1,$P2,$P3"   "$KERNEL_REPO/kernel/dtb-variants/x1p64100-microsoft-denali-edponly.dts"
