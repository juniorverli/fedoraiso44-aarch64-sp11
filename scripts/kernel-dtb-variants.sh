#!/usr/bin/env bash
# Build the diagnostic DTB variants next to the RPM kernel (DT-only, seconds, no RPM).
#
#   scripts/kernel-dtb-variants.sh [KVER]
#   scripts/kernel-dtb-m6.sh [KVER]   build only M6/M6GPU (requires the M5 reference DTBs)
#
# KVER defaults to the version of the RPMs this repo builds (kernel/base.toml: tag, spec release, series_rev),
# e.g. 7.3.0-65.sp11.3.fc44.aarch64. The variants are DT-only: rebuilt, never patched in the RPM.
# Output: out/dtb-variants/<kver>/qcom/<name>.dtb and <name>.json (source commit, patches, sha256).
#   x1p64100-microsoft-denali-nobl      display-lcd 0001+0002 (no backlight node)       tree out/linux/m3nobl
#   x1p64100-microsoft-denali-parity    0001-0003 + 10 CPUs (MADT) + no system_pd idle state (SS3), from
#                                       kernel/dtb-variants/<name>.dts, record cites the MADT  tree out/linux/m3
#   x1p64100-microsoft-denali-edponly   0001-0003, mdss_dp0/dp1 disabled (H5), from
#                                       kernel/dtb-variants/<name>.dts                  tree out/linux/m3
#   x1p64100-microsoft-denali-m5[gpu]   parity + speakers off [+ GPU off] (D21)        tree out/linux/m3
#   x1p64100-microsoft-denali-m6[gpu]   M5 + Wi-Fi 0001 + USB-C 0001; GPU variant
#                                       staged only, no menu entry                    snapshot out/linux/m6
# The trees are kernel worktrees (branches w/m3nobl = v7.3 + series[0:2], w/m3 = v7.3 + series).
# Owner: kernel worker.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"
kver="${1:-$KERNEL_KVER}"
if [[ $KERNEL_SERIES_REV == 7 ]]; then
  exec "$KERNEL_REPO/scripts/kernel-dtb-m10.sh" "$kver"
fi
if [[ $KERNEL_SERIES_REV == 6 ]]; then
  exec "$KERNEL_REPO/scripts/kernel-dtb-m9.sh" "$kver"
fi
if [[ $KERNEL_SERIES_REV == 5 ]]; then
  exec "$KERNEL_REPO/scripts/kernel-dtb-m8.sh" "$kver"
fi
if [[ $KERNEL_SERIES_REV == 4 ]]; then
  exec "$KERNEL_REPO/scripts/kernel-dtb-m7.sh" "$kver"
fi
base_dtb=$(kernel_toml dtb); outdir="$SP11_OUT/dtb-variants/$kver/qcom"
mkdir -p "$outdir"

# variant_checks NAME DTS BASE-DTS DTB: source-level diff of DTS against BASE-DTS (labels kept, phandle numbers
# ignored) and the S1 effective-status check of the DTB; prints the path of a JSON file with both.
variant_checks() {
  local name=$1 dts=$2 base=$3 dtb=$4 out="$SP11_OUT/build/dtb-variant-$name.checks.json" tree="$SP11_OUT/linux/m3"
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -c "
    set -e; cd /tmp/home
    pp() { gcc -E -nostdinc -I $KERNEL_REPO/kernel/dtb-variants -I $tree/arch/arm64/boot/dts/qcom -I $tree/arch/arm64/boot/dts -I $tree/arch/arm64/boot/dts/include -I $tree/include -undef -D__DTS__ -x assembler-with-cpp -o \$1.i \$2; dtc -I dts -O dts -qq -o \$1.dts \$1.i 2>/dev/null; grep -v '^[[:space:]]*phandle = ' \$1.dts > \$1.np; }
    pp base $base; pp var $dts
    diff base.np var.np > diff.txt || true
    dtc -I dtb -O dts -q $dtb > eff.dts 2>/dev/null
    python3 -I $KERNEL_REPO/scripts/kernel-dtb-safety.py eff.dts --also=gpu@3d00000 --also=gmu@3d6a000 --also=zap-shader > safety.json || true
    python3 -I - <<PY
import json
print(json.dumps({'diff_vs_base': {'base': '$base'.split('/')[-1], 'lines': [l.rstrip() for l in open('diff.txt')]},
                  's1_effective_status': json.load(open('safety.json'))}, indent=1))
PY
  " > "$out"
  echo "$out"
}

build() {   # name tree-id patches-description overlay-or-empty [evidence-json-file]
  local dtv=skipped extra="" name=$1 id=$2 patches=$3 overlay=$4 evidence=${5:-} src="$SP11_OUT/linux/$2" built dtbfile sum
  if [[ -n $overlay ]]; then
    # --check = CHECK_DTBS=y (dt-validate against the 7.3 bindings); warnings name the DTB file
    "$KERNEL_REPO/scripts/kernel-dev.sh" --check "$id" variant "$overlay" 2>&1 | tee "$SP11_OUT/build/dtb-variant-$name.log" | grep -E 'kernel-dev:|DTC|rror' || true
    dtv=$(grep -c "$name.dtb:" "$SP11_OUT/build/dtb-variant-$name.log" || true)
    built="$SP11_OUT/build/dev-$id/arch/arm64/boot/dts/qcom/$name.dtb"
  else
    "$KERNEL_REPO/scripts/kernel-dev.sh" "$id" dtbs
    built="$SP11_OUT/build/dev-$id/arch/arm64/boot/dts/$base_dtb"
  fi
  cp -f "$built" "$outdir/$name.dtb"
  if [[ -n ${DIFF_BASE:-} ]]; then extra=$(variant_checks "$name" "$overlay" "$DIFF_BASE" "$outdir/$name.dtb"); fi
  sum=$(sha256sum "$outdir/$name.dtb" | cut -d' ' -f1)
  SERIES_REV=$KERNEL_SERIES_REV EVIDENCE=$evidence DT_VALIDATE=$dtv EXTRA=$extra python3 -I - "$outdir/$name.json" "$name" "$kver" "$id" "$(git -C "$src" rev-parse HEAD)" "$patches" \
      "${overlay:+$(sha256sum "$overlay" | cut -d' ' -f1)}" "${overlay:+${overlay#$KERNEL_REPO/}}" "$sum" \
      "$(git -C "$src" log --reverse --format=%s v7.3..HEAD | paste -sd'|')" <<'PY'
import json, os, sys
out, name, kver, tree, commit, patches, ovsha, ovpath, sha, subjects = sys.argv[1:11]
json.dump({"name": name, "kver": kver, "base": "v7.3 c03c1a14507dfaf8b856c2608f9ac216021fc222",
           "series_rev": int(os.environ["SERIES_REV"]), "kernel_tree": f"out/linux/{tree}", "source_commit": commit,
           "patches_applied": patches.split(","), "patch_subjects": subjects.split("|"),
           "dt_validate_warning_lines": os.environ["DT_VALIDATE"],
           "checks": json.load(open(os.environ["EXTRA"])) if os.environ.get("EXTRA") else None, "overlay": ovpath or None, "evidence": json.load(open(os.environ["EVIDENCE"])) if os.environ.get("EVIDENCE") else None, "overlay_sha256": ovsha or None,
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

# Evidence for parity (a): MADT GICC entries of this unit, decoded with iasl from apic.dat.
ev=$(mktemp); trap 'rm -f "$ev"' EXIT
cat > "$ev" <<JSON
{"source": "sources/windows/live-inventory/acpi/apic.dat", "apic_dat_sha256": "50b032d657ad12b06793d4de71f0425d93a143fbf45965645203b40009a038d0",
 "decoded_with": "iasl -d (Fedora 44 acpica-tools); sources/windows/live-inventory/acpi/apic.dsl",
 "gicc_entries": 12,
 "disabled": [{"processor_uid": 7, "mpidr": "0x10300", "enabled": 0, "dt_node": "cpu@10300 (cpu7)"},
              {"processor_uid": 11, "mpidr": "0x20300", "enabled": 0, "dt_node": "cpu@20300 (cpu11)"}],
 "grade": "Verified (MADT); which cores are fused off was TBD in hardware/soc-boot/README.md Q1",
 "also_checked_against": "previous project patch 0019 (same two MPIDRs); system_pd change = its 0018+0025 net result"}
JSON
build x1p64100-microsoft-denali-parity m3 "$P1,$P2,$P3" "$KERNEL_REPO/kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts" "$ev"

# M5 (D21): parity + speakers off (S1) [+ GPU off]. Diff and S1 check against the parity DTS.
P=$KERNEL_REPO/kernel/dtb-variants
DIFF_BASE=$P/x1p64100-microsoft-denali-parity.dts
build x1p64100-microsoft-denali-m5    m3 "$P1,$P2,$P3" "$P/x1p64100-microsoft-denali-m5.dts"
build x1p64100-microsoft-denali-m5gpu m3 "$P1,$P2,$P3" "$P/x1p64100-microsoft-denali-m5gpu.dts"

# M6: M3 + Wi-Fi/USB-C patches, M5 safety/parity overrides; GPU variant has no menu entry.
"$KERNEL_REPO/scripts/kernel-dtb-m6.sh" "$kver"
