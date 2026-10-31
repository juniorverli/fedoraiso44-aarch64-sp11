#!/usr/bin/env bash
# Compose the scratch kernel tree used by build-spectra.sh: Linux v7.3 + the full kernel/series, configured like
# kernel/config (defconfig + sp11.config + dev.config, as scripts/kernel-dev.sh does), modules_prepare done.
#
#   hardware/cameras/spectra/scripts/prep-tree.sh tree      # host: git worktree out/linux/spectra + apply the series
#   hardware/cameras/spectra/scripts/prep-tree.sh config    # container: .config in out/build/dev-spectra + modules_prepare
#   hardware/cameras/spectra/scripts/prep-tree.sh driver    # host: clone out/ref/camera-driver, apply hardware/cameras/spectra/patches
#   hardware/cameras/spectra/scripts/prep-tree.sh symvers <camera_x1e80100.o>
#                                                           # host: out/build/dev-spectra/extra.symvers for symbols the borrowed
#                                                           # Module.symvers lacks, each checked against EXPORT_SYMBOL in the tree
#
# Three patches of kernel/series (touch-pen 0016, usb-typec 0002, dsp-subsystems 0001) carry no From: header, so
# `git am` refuses them; they are applied with `git apply` and committed with a placeholder message.
# Module.symvers: modpost needs the exported-symbol list of the kernel, which only a vmlinux build produces and a
# full build is out of scope here. Copy one from an earlier dev build of the same series when it exists
# (out/build/dev-touch-pen/Module.symvers was used); without it modpost only warns (KBUILD_MODPOST_WARN=1).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
M="$(dirname "$(readlink -f "$REPO/out")")"
SRC=$M/out/linux/spectra; O=$M/out/build/dev-spectra
case ${1:-} in
  tree)
    git -C "$M/sources/linux" worktree add -b w/spectra ../../out/linux/spectra v7.3
    export GIT_AUTHOR_NAME=spectra GIT_AUTHOR_EMAIL=spectra@localhost GIT_COMMITTER_NAME=spectra GIT_COMMITTER_EMAIL=spectra@localhost
    cd "$SRC"; n=0
    while IFS= read -r p; do
      p="${p%%#*}"; p="${p//[[:space:]]/}"; [[ -n $p ]] || continue; n=$((n + 1))
      if grep -q '^From: ..*<.*>' "$REPO/$p"; then git am -q --3way "$REPO/$p"
      else git apply --index "$REPO/$p" && git commit -q -m "series $n $(basename "$p")"; fi
    done < "$REPO/kernel/series"
    echo "applied $n patches" ;;
  config)
    if [[ ${SP11_IN_CONTAINER:-} != 1 ]]; then
      exec 9>"$M/out/.kernel-build.lock"; flock -w 14400 9
      exec "$REPO/scripts/kernel-container.sh" run "$HERE/prep-tree.sh" config
    fi
    mkdir -p "$O"; cd "$SRC"
    make -s O="$O" ARCH=arm64 defconfig
    scripts/kconfig/merge_config.sh -m -O "$O" "$O/.config" "$REPO/kernel/config/sp11.config" "$REPO/kernel/config/dev.config" >/dev/null
    make -s O="$O" ARCH=arm64 olddefconfig
    "$REPO/scripts/kernel-config-check" -f "$REPO/kernel/config/sp11.config" "$O/.config" || echo "config check: see above (dev.config overrides are expected)"
    make O="$O" ARCH=arm64 -j4 modules_prepare ;;
  driver)
    D=$M/out/build/spectra-camera-driver
    git clone -q "$M/out/ref/camera-driver" "$D"; cd "$D"
    git -c user.name=spectra -c user.email=spectra@localhost am -q "$HERE"/../patches/*.patch ;;
  symvers)
    # The borrowed Module.symvers comes from a kernel built without tracing/BPF events; this config has both, so the
    # module's trace events need bpf_trace_run*, trace_event_* ... Prove each missing symbol is exported by the tree,
    # then list it for KBUILD_EXTRA_SYMBOLS. bpf_trace_run<N> is exported by a macro, so it is matched by prefix.
    obj=${2:?object file}; cd "$SRC"; tmp=$(mktemp -d)
    nm -u "$obj" | awk '{print $2}' | sort -u > "$tmp/undef"
    awk '{print $2}' "$O/Module.symvers" | sort -u > "$tmp/have"
    comm -23 "$tmp/undef" "$tmp/have" | grep -v '^__this_module$' > "$tmp/missing"
    : > "$O/extra.symvers"
    while read -r sym; do
      if grep -rqE "EXPORT_SYMBOL(_GPL)?\(\s*${sym}\s*\)|EXPORT_SYMBOL_GPL\(bpf_trace_run##" --include=*.c kernel lib drivers/base; then
        printf '0x00000000\t%s\tvmlinux\tEXPORT_SYMBOL_GPL\t\n' "$sym" >> "$O/extra.symvers"
      else echo "NOT EXPORTED BY THE TREE: $sym" >&2; fi
    done < "$tmp/missing"
    wc -l "$O/extra.symvers"; rm -rf "$tmp" ;;
  *) sed -n 2,8p "$0"; exit 2 ;;
esac
