# shellcheck shell=bash
# Shared settings for scripts/kernel-*. Sourced, never run. Owner: kernel worker.

KERNEL_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"          # this checkout or worktree
SP11_MAIN="${SP11_MAIN:-$(dirname "$(readlink -f "$KERNEL_REPO/out")")}" # main checkout holding out/ and sources/
SP11_OUT="$SP11_MAIN/out"
KERNEL_TREE="${KERNEL_TREE:-$SP11_OUT/linux/kernel}"                    # kernel worktree, branch w/kernel
KERNEL_BUILD_DIR="$SP11_OUT/build/kernel"
KERNEL_RPMS_DIR="$SP11_OUT/rpms"
KERNEL_LOCK="$SP11_OUT/.kernel-build.lock"

KERNEL_IMAGE="${KERNEL_IMAGE:-sp11-kernel-fc44}"
KERNEL_BASE_IMAGE="registry.fedoraproject.org/fedora:44"

# Fedora kernel.spec switches (checked against kernel-7.3.0-65.fc46.src.rpm, see kernel/base.toml).
# "--with vanilla" sets nopatches=1: the Red Hat patch is not applied (spec line 396).
# NOT `--without debuginfo`: spec line 2370 then rewrites CONFIG_DEBUG_INFO*=y to "is not set", which drops BTF (D2).
# The rest keeps only the 4k base kernel: no debug/rt/64k variants, no perf/tools/selftests/docs.
KERNEL_RPM_SWITCHES=(
  --with vanilla --with baseonly
  --without arm64_64k --without doc --without selftests
  --without cross_headers --without kabidwchk --without kernel_abi_stablelists
  --without perf --without libperf --without tools --without ynl
)

kernel_toml() {   # kernel_toml KEY: value of KEY in kernel/base.toml
  sed -n -E "s/^$1[[:space:]]*=[[:space:]]*\"?([^\"#]*[^\"# ])\"?[[:space:]]*(#.*)?\$/\1/p" "$KERNEL_REPO/kernel/base.toml" | head -1
}
# Series hash: sha256 over "<path> <sha256 of patch>" lines of kernel/series, in order (comments and blanks skipped).
kernel_series_hash() {
  local p
  if [[ -f $KERNEL_REPO/kernel/series ]]; then
    while IFS= read -r p; do
      p="${p%%#*}"; p="${p//[[:space:]]/}"
      if [[ -n $p ]]; then echo "$p $(sha256sum < "$KERNEL_REPO/$p" | cut -d' ' -f1)"; fi
    done < "$KERNEL_REPO/kernel/series"
  fi | sha256sum | cut -d' ' -f1
}
# Fails if kernel/series (or a patch in it) changed without a new series_rev + series_sha256 in base.toml.
kernel_series_check() {
  local want have
  want=$(kernel_toml series_sha256); have=$(kernel_series_hash)
  [[ $have == "$want" ]] || die "kernel/series (or a patch in it) changed: sha256 $have, but kernel/base.toml series_sha256 is ${want:-unset}. Bump series_rev and set series_sha256 = \"$have\" in kernel/base.toml."
}
# Fedora `buildid` mechanism: release 65.sp11.<series_rev>.fc44. series_rev 0 = M1 (empty series), 3 = M3.
KERNEL_SERIES_REV=$(kernel_toml series_rev)
[[ $KERNEL_SERIES_REV =~ ^[0-9]+$ ]] || { echo "kernel: series_rev missing or not an integer in kernel/base.toml" >&2; exit 1; }
KERNEL_BUILDID=".sp11.$KERNEL_SERIES_REV"
KERNEL_DIST=".fc44"
# Expected kernel version string of the RPMs: <tag>.0-<spec release><buildid><dist>.aarch64
KERNEL_KVER="$(kernel_toml tag | sed 's/^v//').0-$(kernel_toml nevra | sed -E 's/^kernel-[0-9.]+-([0-9]+)\..*/\1/')$KERNEL_BUILDID$KERNEL_DIST.aarch64"

die() { echo "kernel: $*" >&2; exit 1; }

# D14: persistent ccache, used through Fedora's compiler wrappers (/usr/lib64/ccache/gcc ...) on PATH.
KERNEL_CCACHE_DIR="$SP11_OUT/ccache"
kernel_ccache_env() {   # call inside the container
  mkdir -p "$KERNEL_CCACHE_DIR"
  export CCACHE_DIR="$KERNEL_CCACHE_DIR" CCACHE_MAXSIZE=15G
  # The tarball is unpacked anew for every rpmbuild: header mtimes/ctimes are new, contents are not.
  export CCACHE_SLOPPINESS=include_file_mtime,include_file_ctime,time_macros
  # Hash the compiler and the redhat-hardened/annobin spec files by content, not by mtime.
  export CCACHE_COMPILERCHECK=content
  # The rpmbuild tree is named after the kernel version (linux-<kver>), which changes with series_rev; the
  # cwd must not enter the hash, or every series_rev bump rebuilds everything. DW_AT_comp_dir in cached
  # objects may name an older directory; find-debuginfo rewrites it to /usr/src/debug.
  export CCACHE_NOHASHDIR=1
  export PATH="/usr/lib64/ccache:$PATH"
}

# ---------------------------------------------------------------------------------------
# Disk guard. On WSL2 the ext4 root lives in a VHDX that grows on the Windows drive. Linux `df /`
# can show plenty free while the VHDX cannot grow, and then writes stall and the VM dies.
# Real headroom = free bytes on the Windows drive + (VHDX file size - bytes used on /).
# Not on WSL (no VHDX found): headroom = `df /` available bytes.
# Overrides: SP11_VHDX=<path>, SP11_MIN_HEADROOM_GIB=<n> (start threshold), SP11_STOP_HEADROOM_GIB=<n>.
KERNEL_GIB=$((1024 * 1024 * 1024))
KERNEL_STOP_GIB="${SP11_STOP_HEADROOM_GIB:-15}"

kernel_find_vhdx() {   # prints the path of the VHDX holding / , or nothing
  local used f best="" bsize=0 sz
  if [[ -n ${SP11_VHDX:-} ]]; then [[ -f $SP11_VHDX ]] && echo "$SP11_VHDX"; return 0; fi
  used=$(df -B1 --output=used / | tail -1 | tr -d ' ')
  for f in /mnt/c/Users/*/AppData/Local/Packages/*/LocalState/ext4.vhdx \
           /mnt/c/Users/*/AppData/Local/wsl/*/ext4.vhdx; do
    [[ -f $f ]] || continue
    sz=$(stat -c %s "$f")
    # plausible: at least as large as the bytes used on /; among those the smallest
    ((sz >= used)) || continue
    if [[ -z $best ]] || ((sz < bsize)); then best=$f; bsize=$sz; fi
  done
  if [[ -n $best ]]; then echo "$best"; fi
  return 0
}

# Prints "headroom_bytes source".
kernel_headroom() {
  local vhdx cfree vsize used room
  vhdx=$(kernel_find_vhdx)
  if [[ -n $vhdx && -d /mnt/c ]]; then
    cfree=$(df -B1 --output=avail /mnt/c | tail -1 | tr -d ' ')
    vsize=$(stat -c %s "$vhdx")
    used=$(df -B1 --output=used / | tail -1 | tr -d ' ')
    room=$((vsize - used)); ((room < 0)) && room=0
    echo "$((cfree + room)) wsl(C:free=$((cfree / KERNEL_GIB))G vhdx=$((vsize / KERNEL_GIB))G used=$((used / KERNEL_GIB))G)"
  else
    echo "$(df -B1 --output=avail / | tail -1 | tr -d ' ') df-root"
  fi
}

# kernel_guard_start <release|dev>: refuse below the profile threshold.
kernel_guard_start() {
  local profile=$1 min h src
  case $profile in release) min=60 ;; dev) min=20 ;; *) die "guard: unknown profile $profile" ;; esac
  if [[ -n ${SP11_MIN_HEADROOM_GIB:-} ]]; then
    echo "kernel: WARNING: start threshold overridden to ${SP11_MIN_HEADROOM_GIB} GiB (default $min). The disk may fill and kill WSL." >&2
    min=$SP11_MIN_HEADROOM_GIB
  fi
  read -r h src < <(kernel_headroom)
  echo "kernel: disk headroom $((h / KERNEL_GIB)) GiB [$src], need >= $min GiB for $profile"
  ((h >= min * KERNEL_GIB)) || die "REFUSED: headroom $((h / KERNEL_GIB)) GiB < $min GiB [$src]. Free space on the Windows drive or inside the VHDX, or set SP11_MIN_HEADROOM_GIB at your own risk."
}

# kernel_watchdog_start <container-name> <logfile>: samples every 15 s; below the stop threshold
# it logs the reason, writes the flag file and kills the container. Sets KERNEL_WATCHDOG_PID.
KERNEL_WATCHDOG_FLAG="$SP11_OUT/build/.watchdog-stopped"
kernel_watchdog_start() {
  local name=$1 log=$2
  mkdir -p "$SP11_OUT/build"
  rm -f "$KERNEL_WATCHDOG_FLAG" "$KERNEL_WATCHDOG_FLAG.min"
  (
    local h src msg min_h=-1
    while sleep "${SP11_WATCHDOG_INTERVAL:-15}"; do
      read -r h src < <(kernel_headroom)
      if ((min_h < 0 || h < min_h)); then min_h=$h; echo "$min_h" > "$KERNEL_WATCHDOG_FLAG.min"; fi
      if ((h < KERNEL_STOP_GIB * KERNEL_GIB)); then
        msg="kernel: WATCHDOG STOP $(date -u +%FT%TZ): headroom $((h / KERNEL_GIB)) GiB < ${KERNEL_STOP_GIB} GiB [$src]; killing container $name"
        echo "$msg" | tee -a "$log" >&2
        echo "$msg" > "$KERNEL_WATCHDOG_FLAG"
        docker kill "$name" >/dev/null 2>&1 || true
        exit 0
      fi
    done
  ) &
  KERNEL_WATCHDOG_PID=$!
}
# Returns 1 (and prints the reason) if the watchdog stopped the build.
kernel_watchdog_stop() {
  if [[ -n ${KERNEL_WATCHDOG_PID:-} ]]; then kill "$KERNEL_WATCHDOG_PID" 2>/dev/null || true; fi
  if [[ -s $KERNEL_WATCHDOG_FLAG ]]; then cat "$KERNEL_WATCHDOG_FLAG" >&2; return 1; fi
  return 0
}
