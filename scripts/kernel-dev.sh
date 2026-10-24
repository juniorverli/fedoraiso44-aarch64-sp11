#!/usr/bin/env bash
# Dev profile (D14): incremental kernel builds with a small footprint. Not for ISOs: RPMs come
# from kernel-build.sh (release profile).
#
#   scripts/kernel-dev.sh [-j N] [--check] <id> [dtbs | module <path> | all]
#
#   <id>            sources: out/linux/<id> (a git worktree of the kernel tree);
#                   objects: out/build/dev-<id> (make O=...)
#   dtbs            (default) build only the DTB named in kernel/base.toml
#   module <path>   build one module dir or .ko (builds vmlinux first if needed)
#   all             Image, DTBs and modules (no RPM)
#   --check         add CHECK_DTBS=y (dt-schema validation) to dtbs
#
# Config: upstream arm64 `defconfig` + kernel/config/sp11.config (BTF on, D2) + kernel/config/dev.config
# (dev-only fixes: defconfig's DEBUG_INFO_REDUCED blocks BTF), merged with the tree's
# scripts/kconfig/merge_config.sh. SP11_DEV_FRAGMENT=<file> adds one more fragment (experiments).
# Runs in the Fedora 44 container, through ccache (out/ccache), under out/.kernel-build.lock.
# Disk guard: start needs 20 GiB headroom, watchdog stops below 15 GiB (kernel-common.sh).
# Prints elapsed time and the size of the O= dir. Owner: kernel worker.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"

jobs=6 check=0 inner=0
while (($#)); do
  case $1 in
    -j) jobs=$2; shift 2 ;;
    --check) check=1; shift ;;
    --inner) inner=1; shift ;;
    -h|--help) sed -n 2,19p "$0"; exit 0 ;;
    *) break ;;
  esac
done
id=${1:-}; [[ -n $id ]] || die "usage: kernel-dev.sh [-j N] [--check] <id> [dtbs|module <path>|all]"
mode=${2:-dtbs}; arg=${3:-}
src="$SP11_OUT/linux/$id"; O="$SP11_OUT/build/dev-$id"
dtb=$(sed -n -E 's/^dtb[[:space:]]*=[[:space:]]*"([^"]*)".*/\1/p' "$KERNEL_REPO/kernel/base.toml")
((jobs >= 1 && jobs <= 6)) || die "-j must be 1..6"
[[ -d $src ]] || die "no kernel worktree $src"

if ((inner)); then
  kernel_ccache_env; ccache -z >/dev/null
  frag="$KERNEL_REPO/kernel/config/sp11.config"
  devfrag="$KERNEL_REPO/kernel/config/dev.config"
  extra_frag="${SP11_DEV_FRAGMENT:-}"
  want=$(cat "$frag" "$devfrag" ${extra_frag:+"$extra_frag"} | sha256sum | cut -d' ' -f1)
  mkdir -p "$O"
  if [[ ! -f $O/.config || $(cat "$O/.config.sp11-sha" 2>/dev/null) != "$want" ]]; then
    ( cd "$src"
      make -s O="$O" ARCH=arm64 defconfig
      scripts/kconfig/merge_config.sh -m -O "$O" "$O/.config" "$frag" "$devfrag" ${extra_frag:+"$extra_frag"} >/dev/null
      make -s O="$O" ARCH=arm64 olddefconfig )
    # expected = sp11.config with the symbols dev.config overrides replaced by dev.config's values
    exp="$O/.expected.config"
    syms=$(sed -n -E 's/^(# )?(CONFIG_[A-Z0-9_]+)[ =].*/\2/p' "$devfrag" | paste -sd'|')
    { grep -v -E "^(# )?($syms)[ =]" "$frag"; cat "$devfrag"; } > "$exp"
    "$KERNEL_REPO/scripts/kernel-config-check" -f "$exp" "$O/.config" \
      || die "fragment symbols did not survive olddefconfig (see $exp)"
    echo "$want" > "$O/.config.sp11-sha"
  fi
  m=(make -C "$src" O="$O" ARCH=arm64 -j"$jobs")
  start=$(date +%s)
  case $mode in
    dtbs)   "${m[@]}" $( ((check)) && echo CHECK_DTBS=y ) "$dtb" ;;
    all)    "${m[@]}" Image dtbs modules ;;
    module)
      [[ -n $arg ]] || die "module needs a path"
      [[ -f $O/vmlinux ]] || { echo "kernel-dev: no vmlinux in $O, building it first"; "${m[@]}" vmlinux; }
      [[ -f $O/Module.symvers ]] || "${m[@]}" modules_prepare
      t=${arg%/}; [[ $t == *.ko ]] || t="$t/"
      "${m[@]}" "$t" ;;
    *) die "unknown mode $mode" ;;
  esac
  end=$(date +%s)
  echo "kernel-dev: $id $mode ${arg} took $((end - start)) s (-j$jobs), O= $(du -sh "$O" | cut -f1)"
  ccache --print-stats | grep -E '^(direct_cache_hit|preprocessed_cache_hit|cache_miss)\s' | tr '\n\t' '  ' ; echo
  exit 0
fi

mkdir -p "$SP11_OUT/build"
exec 9>"$KERNEL_LOCK"
flock -w 14400 9 || die "no build lock after 4 h"
kernel_guard_start dev
export KERNEL_CONTAINER_NAME="sp11-kernel-dev-$id-$$"
log="$SP11_OUT/build/dev-$id.log"
kernel_watchdog_start "$KERNEL_CONTAINER_NAME" "$log"
trap 'docker kill "$KERNEL_CONTAINER_NAME" >/dev/null 2>&1 || true; kernel_watchdog_stop || true' INT TERM
set +e
"$KERNEL_REPO/scripts/kernel-container.sh" run "$KERNEL_REPO/scripts/kernel-dev.sh" -j "$jobs" \
  $( ((check)) && echo --check ) --inner "$id" "$mode" ${arg:+"$arg"} 2>&1 | tee "$log"
rc=${PIPESTATUS[0]}
set -e
kernel_watchdog_stop || die "build stopped by the disk watchdog, see $log"
exit "$rc"
