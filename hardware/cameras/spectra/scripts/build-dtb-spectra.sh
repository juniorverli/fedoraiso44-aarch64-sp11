#!/usr/bin/env bash
# Build the Spectra DTB variant x1p64100-microsoft-denali-m15-spectra from kernel/dtb-variants/ on a scratch tree
# (v7.3 + the full kernel/series + ec-sam 0005, out/linux/spectra-dt), with CHECK_DTBS=y, without git writes to the
# project and without publishing anything under out/dtb-variants/<kver>/ (the kernel worker owns that).
#
#   hardware/cameras/spectra/scripts/build-dtb-spectra.sh [--tree-only]
#
# Inputs besides the variant (all in git):
#   hardware/cameras/spectra/dt/qcl/hamoa-camera.dtsi            Qualcomm's DT, pinned in dt/qcl/SOURCE.txt
#   hardware/cameras/spectra/dt/include/dt-bindings/camera/msm-camera.h   from camera-driver 08171dd (GPL-2.0-only)
# Both are copied into the scratch tree for the build and removed after (the kernel worker must carry them in its
# kernel tree: dtsi in arch/arm64/boot/dts/qcom/, header in include/dt-bindings/camera/).
# kernel/dtb-variants has no m15-safe yet (kernel worker, series_rev 12): a stand-in with the same content as
# m14-safe (m12 + microphones) is staged, and a pass-through parity shim like scripts/kernel-dtb-m14.sh does.
# Output: out/dtb-variants/spectra-test/qcom/x1p64100-microsoft-denali-m15-spectra.{dtb,json}
# Runs the dev kernel build container under the kernel build lock (scripts/kernel-dev.sh).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
. "$REPO/scripts/kernel-common.sh"
ID=spectra-dt
SRC="$SP11_OUT/linux/$ID"
STAGE="$SP11_OUT/build/dtb-spectra-stage"
OUT="$SP11_OUT/dtb-variants/spectra-test/qcom"
NAME=x1p64100-microsoft-denali-m15-spectra
DT="$REPO/hardware/cameras/spectra/dt"
series_hash=$(kernel_series_hash)
ecsam5=$(ls "$REPO"/hardware/ec-sam/patches/0005-*.patch)

prep_tree() {
  if [[ -d $SRC ]]; then
    [[ $(cat "$SRC/.spectra-dt-series" 2>/dev/null) == "$series_hash $(sha256sum < "$ecsam5" | cut -d' ' -f1)" ]] \
      || die "$SRC exists but was composed from another series; remove it with: git -C $SP11_MAIN/sources/linux worktree remove --force ../../out/linux/$ID"
    return
  fi
  git -C "$SP11_MAIN/sources/linux" worktree add --detach "../../out/linux/$ID" v7.3
  export GIT_AUTHOR_NAME=spectra GIT_AUTHOR_EMAIL=spectra@localhost GIT_COMMITTER_NAME=spectra GIT_COMMITTER_EMAIL=spectra@localhost
  local p n=0
  ( cd "$SRC"
    while IFS= read -r p; do
      p="${p%%#*}"; p="${p//[[:space:]]/}"; [[ -n $p ]] || continue; n=$((n + 1))
      if grep -q '^From: ..*<.*>' "$REPO/$p"; then git am -q --3way "$REPO/$p"
      else git apply --index "$REPO/$p" && git commit -q -m "series $n $(basename "$p")"; fi
    done < "$REPO/kernel/series"
    git apply --index "$ecsam5" && git commit -q -m "ec-sam 0005 (volume keys DT, not yet in kernel/series)"
    echo "applied $n series patches + ec-sam 0005" )
  echo "$series_hash $(sha256sum < "$ecsam5" | cut -d' ' -f1)" > "$SRC/.spectra-dt-series"
}
prep_tree
[[ ${1:-} == --tree-only ]] && exit 0

q=$SRC/arch/arm64/boot/dts/qcom
rm -rf "$STAGE"; mkdir -p "$STAGE" "$OUT"
cp "$REPO"/kernel/dtb-variants/*.dts "$STAGE/"
cat > "$STAGE/x1p64100-microsoft-denali-parity.dts" <<'DTS'
// SPDX-License-Identifier: BSD-3-Clause
/* Parity is supplied by the integrated LCD board patch. */
#include "x1p64100-microsoft-denali.dts"
DTS
[[ -f $STAGE/x1p64100-microsoft-denali-m15-safe.dts ]] || cat > "$STAGE/x1p64100-microsoft-denali-m15-safe.dts" <<'DTS'
// SPDX-License-Identifier: BSD-3-Clause
/* Stand-in until the kernel worker publishes m15-safe: same content as m14-safe (m12 + microphones, GPU off). */
#include "x1p64100-microsoft-denali-m14-safe.dts"
DTS
mkdir -p "$SRC/include/dt-bindings/camera"
cp "$DT/qcl/hamoa-camera.dtsi" "$q/"
cp "$DT/include/dt-bindings/camera/msm-camera.h" "$SRC/include/dt-bindings/camera/"
trap 'rm -f "$q/hamoa-camera.dtsi" "$SRC/include/dt-bindings/camera/msm-camera.h"; rmdir "$SRC/include/dt-bindings/camera" 2>/dev/null || true' EXIT
log="$SP11_OUT/build/dtb-spectra.log"
rm -f "$SP11_OUT/build/dev-$ID/arch/arm64/boot/dts/qcom/$NAME.dtb"
"$REPO/scripts/kernel-dev.sh" --check "$ID" variant "$STAGE/$NAME.dts" 2>&1 | tee "$log"
built="$SP11_OUT/build/dev-$ID/arch/arm64/boot/dts/qcom/$NAME.dtb"
[[ -f $built ]] || die "no DTB built, see $log"
diag=$(grep -cE "^(arch/arm64/boot/dts/qcom/)?$NAME\.dtb:|Warning \(" "$log" || true)
cp "$built" "$OUT/$NAME.dtb"
python3 -I - "$REPO" "$OUT" "$NAME" "$log" "$diag" "$series_hash" "$SRC" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
repo, out, name, log, diag, series, src = sys.argv[1:8]
repo, out = Path(repo), Path(out)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rec = dict(name=name, series_hash_sha256=series, ec_sam_0005=True, kernel_tree='out/linux/spectra-dt',
           tree_head=subprocess.check_output(['git', '-C', src, 'rev-parse', 'HEAD'], text=True).strip(),
           check_dtbs_diagnostic_lines=int(diag), build_log=log,
           variant_sha256=sha(repo / f'kernel/dtb-variants/{name}.dts'),
           qualcomm_dtsi_sha256=sha(repo / 'hardware/cameras/spectra/dt/qcl/hamoa-camera.dtsi'),
           msm_camera_h_sha256=sha(repo / 'hardware/cameras/spectra/dt/include/dt-bindings/camera/msm-camera.h'),
           dtb=f'qcom/{name}.dtb', sha256=sha(out / f'{name}.dtb'),
           stand_in=['m15-safe = m14-safe content', 'parity = pass-through shim'])
(out / f'{name}.json').write_text(json.dumps(rec, indent=2) + '\n')
print(json.dumps(rec, indent=2))
PY
