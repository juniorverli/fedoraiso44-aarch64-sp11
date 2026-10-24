#!/usr/bin/env bash
# Build the Fedora kernel RPMs: Fedora's kernel.spec, vanilla mode (D13), v7.3 tarball (D1),
# kernel/config/sp11.config as the spec's `kernel-local` fragment, kernel/series as spec patches.
# Runs rpmbuild in the Fedora 44 container (D12) under out/.kernel-build.lock.
#
#   scripts/kernel-build.sh [-j N] [--prepare-only] [--check-only]
#
#   -j N            parallel jobs, 1..6 (default 6; the host has 10 cores and ~12 GB RAM)
#   --prepare-only  fill out/build/kernel/rpmbuild (spec, tarball, config, patches) and stop
#   --check-only    skip rpmbuild, run scripts/kernel-check on the last build
#
# Inputs: kernel/base.toml, kernel/config/sp11.config, kernel/series. Nothing else.
# The lock is held only while rpmbuild runs. A disk guard refuses to start below 60 GiB real headroom
# (WSL: Windows drive free + VHDX slack) and a watchdog stops the build below 15 GiB (kernel-common.sh).
# Output: out/rpms/*.rpm, out/rpms/<nevra>.json, out/build/kernel/rpmbuild.log.
# Owner: kernel worker.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"

TOPDIR="$KERNEL_BUILD_DIR/rpmbuild"
BASE_TOML="$KERNEL_REPO/kernel/base.toml"
jobs=6 prepare_only=0 check_only=0 inner=0
while (($#)); do
  case $1 in
    -j) jobs=$2; shift 2 ;;
    --prepare-only) prepare_only=1; shift ;;
    --check-only) check_only=1; shift ;;
    --inner) inner=1; shift ;;
    -h|--help) sed -n 2,15p "$0"; exit 0 ;;
    *) die "unknown option $1" ;;
  esac
done
((jobs >= 1 && jobs <= 6)) || die "-j must be 1..6"

toml() { sed -n -E "s/^$1[[:space:]]*=[[:space:]]*\"?([^\"]*)\"?[[:space:]]*\$/\1/p" "$BASE_TOML" | head -1; }

# ---------------------------------------------------------------------------------------
# inner: runs inside the container, does only rpmbuild + resource accounting
if ((inner)); then
  stats="$KERNEL_BUILD_DIR/build-stats.env"
  kernel_ccache_env
  ccache -z >/dev/null
  ccache --version | head -1
  ( peak=0
    while sleep 3; do
      a=$(awk '$1=="anon"{print $2}' /sys/fs/cgroup/memory.stat 2>/dev/null || echo 0)
      ((a > peak)) && { peak=$a; echo "$peak" > "$KERNEL_BUILD_DIR/mem-anon-peak.bytes"; }
    done ) &
  sampler=$!
  start=$(date +%s)
  rc=0
  rpmbuild -bb --noclean --target aarch64 \
    --define "_topdir $TOPDIR" --define "buildid $KERNEL_BUILDID" --define "dist $KERNEL_DIST" \
    --define "_smp_mflags -j$jobs" --define "_smp_build_ncpus $jobs" \
    "${KERNEL_RPM_SWITCHES[@]}" "$TOPDIR/SPECS/kernel.spec" || rc=$?
  end=$(date +%s)
  kill "$sampler" 2>/dev/null || true
  {
    echo "start=$start"; echo "end=$end"; echo "seconds=$((end - start))"; echo "jobs=$jobs"; echo "rpmbuild_rc=$rc"
    ccache --print-stats | sed -n -E 's/^(direct_cache_hit|preprocessed_cache_hit|cache_miss|files_in_cache|cache_size_kibibyte)\t/ccache_\1=/p'
    echo "mem_cgroup_peak_bytes=$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo 0)"
    echo "mem_anon_peak_bytes=$(cat "$KERNEL_BUILD_DIR/mem-anon-peak.bytes" 2>/dev/null || echo 0)"
  } > "$stats"
  exit "$rc"
fi

# ---------------------------------------------------------------------------------------
# outer: host side
cd "$KERNEL_REPO"
mkdir -p "$KERNEL_BUILD_DIR" "$KERNEL_RPMS_DIR"

if ((check_only)); then exec "$KERNEL_REPO/scripts/kernel-check"; fi

docker image inspect "$KERNEL_IMAGE" >/dev/null 2>&1 || die "no image $KERNEL_IMAGE; run scripts/kernel-container.sh image"
cr() { "$KERNEL_REPO/scripts/kernel-container.sh" run "$@"; }

# 1. source SRPM: pinned by SHA-256
srpm_name=$(toml srpm_file); srpm_sha=$(toml srpm_sha256)
srpm="$SP11_OUT/srpms/$srpm_name"
[[ -f $srpm ]] || { mkdir -p "$SP11_OUT/srpms"; curl -fL -o "$srpm" "$(toml srpm_url)"; }
echo "$srpm_sha  $srpm" | sha256sum -c - >/dev/null || die "SRPM sha256 differs from kernel/base.toml"
if [[ ! -f $TOPDIR/SPECS/kernel.spec || ! -f $TOPDIR/.srpm-$srpm_sha ]]; then
  rm -rf "$TOPDIR"; mkdir -p "$TOPDIR"/{SOURCES,SPECS,BUILD,RPMS,SRPMS,BUILDROOT}
  cr rpm -D "_topdir $TOPDIR" -ivh "$srpm" >/dev/null
  touch "$TOPDIR/.srpm-$srpm_sha"
fi

# 2. vanilla tarball from the pinned tag, as Source0 of the spec
tag=$(toml tag); commit=$(toml commit)
[[ $(git -C "$SP11_MAIN/sources/linux" rev-parse "$tag^{commit}") == "$commit" ]] \
  || die "tag $tag is not $commit in sources/linux"
tarball="$TOPDIR/SOURCES/linux-${tag#v}.tar.xz"
want_tar_sha=$(toml tarball_sha256)
if ! { [[ -f $tarball ]] && echo "$want_tar_sha  $tarball" | sha256sum -c - >/dev/null 2>&1; }; then
  git -C "$SP11_MAIN/sources/linux" archive --format=tar --prefix="linux-${tag#v}/" "$tag" | xz -T4 -6 > "$tarball"
  echo "$want_tar_sha  $tarball" | sha256sum -c - >/dev/null || die "tarball sha256 differs from kernel/base.toml"
fi

# 3. Kconfig fragment: Fedora's own hook for local config changes (spec Source3001 `kernel-local`)
cp "$KERNEL_REPO/kernel/config/sp11.config" "$TOPDIR/SOURCES/kernel-local"

# 4. series -> spec patches (empty series = pure vanilla)
spec="$TOPDIR/SPECS/kernel.spec"
rm -f "$TOPDIR"/SOURCES/sp11-*.patch
[[ -f $TOPDIR/SPECS/kernel.spec.fedora ]] || cp "$spec" "$TOPDIR/SPECS/kernel.spec.fedora"
cp "$TOPDIR/SPECS/kernel.spec.fedora" "$spec"
n=0; defs="" apps=""
if [[ -f kernel/series ]]; then
  while IFS= read -r p; do
    p="${p%%#*}"; p="${p//[[:space:]]/}"; [[ -n $p ]] || continue
    [[ -f $p ]] || die "series: $p does not exist"
    n=$((n + 1)); id=$((2000 + n)); f="sp11-$(printf '%04d' "$n")-$(basename "$p")"
    cp "$p" "$TOPDIR/SOURCES/$f"
    defs+="Patch$id: $f\n"; apps+="ApplyPatch $f\n"
  done < kernel/series
fi
if ((n)); then
  sed -i -e "s|^# END OF PATCH DEFINITIONS|$defs&|" \
         -e "s|^ApplyOptionalPatch linux-kernel-test.patch|&\n$apps|" "$spec"
fi
echo "kernel-build: $n series patch(es)"

if ((prepare_only)); then echo "kernel-build: prepared $TOPDIR"; exit 0; fi

# 5. build, under the shared lock (other workers hold it for their own kernel builds; wait for it)
exec 9>"$KERNEL_LOCK"
echo "kernel-build: waiting for $KERNEL_LOCK"
flock -w 14400 9 || die "no lock after 4 h"
avail_gb=$(free -g | awk '/^Mem:/{print $7}')
kernel_guard_start release
echo "kernel-build: free -g available = ${avail_gb} GB, jobs = $jobs"
((avail_gb >= 4)) || die "only ${avail_gb} GB available, need >= 4; stop other jobs or lower -j"
echo "kernel-build: rpmbuild starts $(date -u +%FT%TZ)"
rm -f "$KERNEL_BUILD_DIR/build-stats.env" "$KERNEL_BUILD_DIR/mem-anon-peak.bytes"
export KERNEL_CONTAINER_NAME="sp11-kernel-release-$$"
kernel_watchdog_start "$KERNEL_CONTAINER_NAME" "$KERNEL_BUILD_DIR/rpmbuild.log"
trap 'docker kill "$KERNEL_CONTAINER_NAME" >/dev/null 2>&1 || true; kernel_watchdog_stop || true' INT TERM
cr "$KERNEL_REPO/scripts/kernel-build.sh" -j "$jobs" --inner 2>&1 | tee "$KERNEL_BUILD_DIR/rpmbuild.log"
rc=${PIPESTATUS[0]}
kernel_watchdog_stop || die "build stopped by the disk watchdog, see $KERNEL_BUILD_DIR/rpmbuild.log"
[[ -f $KERNEL_WATCHDOG_FLAG.min ]] && echo "kernel-build: min headroom seen $(( $(cat "$KERNEL_WATCHDOG_FLAG.min") / KERNEL_GIB )) GiB" | tee -a "$KERNEL_BUILD_DIR/rpmbuild.log"
((rc == 0)) || die "rpmbuild failed (rc=$rc), see $KERNEL_BUILD_DIR/rpmbuild.log"

# 6. collect RPMs, check, record
find "$TOPDIR/RPMS" -name '*.rpm' -exec cp -f {} "$KERNEL_RPMS_DIR/" \;
"$KERNEL_REPO/scripts/kernel-check"
