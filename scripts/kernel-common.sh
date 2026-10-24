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
KERNEL_BUILDID=".sp11"
KERNEL_DIST=".fc44"

die() { echo "kernel: $*" >&2; exit 1; }

# D14: persistent ccache, used through Fedora's compiler wrappers (/usr/lib64/ccache/gcc ...) on PATH.
KERNEL_CCACHE_DIR="$SP11_OUT/ccache"
kernel_ccache_env() {   # call inside the container
  mkdir -p "$KERNEL_CCACHE_DIR"
  export CCACHE_DIR="$KERNEL_CCACHE_DIR" CCACHE_MAXSIZE=30G
  # The tarball is unpacked anew for every rpmbuild: header mtimes/ctimes are new, contents are not.
  export CCACHE_SLOPPINESS=include_file_mtime,include_file_ctime,time_macros
  # Hash the compiler and the redhat-hardened/annobin spec files by content, not by mtime.
  export CCACHE_COMPILERCHECK=content
  export PATH="/usr/lib64/ccache:$PATH"
}
