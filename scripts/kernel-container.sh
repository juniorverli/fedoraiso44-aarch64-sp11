#!/usr/bin/env bash
# Fedora 44 aarch64 build container for the kernel RPMs (D2, D12, D13).
# Nothing is installed on the host: everything runs in registry.fedoraproject.org/fedora:44.
#
#   scripts/kernel-container.sh image [SPEC]   build the image (base tools + BuildRequires of SPEC)
#   scripts/kernel-container.sh run CMD...     run CMD in the container (as the calling user)
#   scripts/kernel-container.sh shell          interactive shell
#
# Mounts the main checkout (out/, sources/linux, the kernel worktree) and this checkout
# at their host paths, so symlinks and git worktree links resolve unchanged.
# Owner: kernel worker.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"

# Packages every kernel build needs, on top of the BuildRequires of kernel.spec.
BASE_PKGS=(dwarves gcc gcc-c++ make bison flex bc openssl-devel elfutils-libelf-devel elfutils-devel
           dtc rpm-build rpmdevtools python3 python3-pyyaml git perl-interpreter perl-generators
           dt-schema dnf-plugins-core util-linux procps-ng cpio xz zstd rsync jq sparse)

cmd_image() {
  local spec="${1:-$KERNEL_BUILD_DIR/rpmbuild/SPECS/kernel.spec}"
  local ctx; ctx="$(mktemp -d)"
  trap 'rm -rf "$ctx"' RETURN
  local builddep=""
  if [[ -f $spec ]]; then
    cp "$spec" "$ctx/kernel.spec"
    local defs=() s v
    for s in "${KERNEL_RPM_SWITCHES[@]}"; do
      case $s in --with) v=with;; --without) v=without;; *) defs+=(--define "_${v}_$s 1");; esac
    done
    printf -v builddep 'dnf -y builddep --define "dist %s" %s /ctx/kernel.spec &&' \
      "$KERNEL_DIST" "$(printf '%q ' "${defs[@]}")"
  else
    echo "kernel-container: no spec at $spec, image has base tools only" >&2
  fi
  cat > "$ctx/Dockerfile" <<DOCKER
FROM $KERNEL_BASE_IMAGE
COPY . /ctx
RUN dnf -y install ${BASE_PKGS[*]} && $builddep dnf clean all && rm -rf /ctx
DOCKER
  docker build --pull -t "$KERNEL_IMAGE" "$ctx"
}

docker_run() {
  local tty=()
  [[ -t 0 && -t 1 ]] && tty=(-it)
  docker run --rm "${tty[@]}" \
    --user "$(id -u):$(id -g)" -e HOME=/tmp/home -e SP11_IN_CONTAINER=1 \
    --tmpfs /tmp/home:exec,mode=1777 \
    -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro \
    -v "$SP11_MAIN:$SP11_MAIN" -v "$KERNEL_REPO:$KERNEL_REPO" \
    -w "$KERNEL_REPO" "$@"
}

case "${1:-}" in
  image) shift; cmd_image "$@" ;;
  run)   shift; docker_run "$KERNEL_IMAGE" "$@" ;;
  shell) docker_run "$KERNEL_IMAGE" bash ;;
  *)     sed -n '2,12p' "$0"; exit 2 ;;
esac
