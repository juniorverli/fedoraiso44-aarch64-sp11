#!/usr/bin/env bash
# Out-of-tree build of Qualcomm's downstream camera-kernel (Spectra, CAMERA_ARCH=x1e80100) against the
# SP11 scratch kernel tree (v7.3 + full kernel/series), without building vmlinux.
#
#   hardware/cameras/spectra/scripts/build-spectra.sh prep          # one-off: clone + tree check (host)
#   hardware/cameras/spectra/scripts/build-spectra.sh build [-k]    # make M=... modules, log to out/build/spectra-build.log
#   hardware/cameras/spectra/scripts/build-spectra.sh obj <path.o>  # one object, for iteration
#   hardware/cameras/spectra/scripts/build-spectra.sh plain         # Kbuild defaults only (SPECTRA_FRESH=1 removes cam_generated_h first)
#
# Layout (all under the main checkout's out/, never in git):
#   out/linux/spectra            kernel worktree, branch w/spectra = v7.3 + kernel/series (69 patches)
#   out/build/dev-spectra        O= dir (defconfig-based .config, modules_prepare done)
#   out/build/spectra-camera-driver   clone of out/ref/camera-driver (08171dd) + our patches
# Runs in the Fedora 44 container (scripts/kernel-container.sh), under the kernel build lock.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
M="$(dirname "$(readlink -f "$REPO/out")")"
SRC=$M/out/linux/spectra; O=$M/out/build/dev-spectra; CAM=${SPECTRA_SRC:-$M/out/build/spectra-camera-driver}
# SPECTRA_SRC=<dir> builds another checkout of the driver; SPECTRA_EXTRA=<file.mk> passes KBUILD_EXTRA_CONFIGS
mode=${1:-build}; shift || true
SPECTRA_FRESH=${SPECTRA_FRESH:-0}
inner() {
  [[ $mode == plain ]] || [[ -f $CAM/cam_generated_h ]] || {
    echo '#define CAMERA_COMPILE_TIME "sp11"'; echo '#define CAMERA_COMPILE_HOST "sp11"'
    echo '#define CAMERA_CC_VERSION "gcc"'; } > "$CAM/cam_generated_h"
  [[ -f $O/extra.symvers ]] && export KBUILD_EXTRA_SYMBOLS=$O/extra.symvers   # see prep-tree.sh: stand-in for vmlinux's Module.symvers
  args=(-C "$SRC" O="$O" ARCH=arm64 M="$CAM" CAMERA_KERNEL_ROOT="$CAM" KERNEL_ROOT="$SRC" CAMERA_ARCH=x1e80100
        ${SPECTRA_EXTRA:+KBUILD_EXTRA_CONFIGS=$SPECTRA_EXTRA} -j6)
  case $mode in
    plain) # only M= and CAMERA_ARCH=, as a distribution or DKMS build would (needs the Kbuild patches)
      [[ -f $CAM/cam_generated_h && $SPECTRA_FRESH == 1 ]] && rm -f "$CAM/cam_generated_h"
      make -C "$SRC" O="$O" ARCH=arm64 M="$CAM" CAMERA_ARCH=x1e80100 -j6 "$@" modules ;;
    build) make "${args[@]}" "$@" modules ;;
    obj)   make "${args[@]}" "$@" ;;
  esac
}
if [[ ${SP11_IN_CONTAINER:-} == 1 ]]; then inner "$@"; exit; fi
exec 9>"$M/out/.kernel-build.lock"; flock -w 14400 9
log=${SPECTRA_LOG:-$M/out/build/spectra-build.log}
"$REPO/scripts/kernel-container.sh" run env SPECTRA_SRC="${SPECTRA_SRC:-}" SPECTRA_EXTRA="${SPECTRA_EXTRA:-}" SPECTRA_LOG="${SPECTRA_LOG:-}" SPECTRA_FRESH="${SPECTRA_FRESH:-0}" "$HERE/build-spectra.sh" "$mode" "$@" 2>&1 | tee "$log"
