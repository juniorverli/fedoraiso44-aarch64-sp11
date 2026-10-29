#!/usr/bin/env bash
# Fedora 44 aarch64 build/test container of the image worker (D11, D12).
#   scripts/image-container.sh build            build the image sp11-fedora-image:44
#   scripts/image-container.sh run CMD [ARGS]   run CMD inside it (privileged)
#   scripts/image-container.sh shell            interactive shell
#
# Inside the container: the repository (this worktree) is /sp11, the shared
# out/ directory of the main checkout is /out, and SP11_OUT=/out. Scripts use
# ${SP11_OUT:-<repo>/out}. Privileged because livemedia-creator needs loop
# devices and mounts. Nothing is installed on the host.
set -euo pipefail

IMAGE=${SP11_IMAGE_CONTAINER:-sp11-fedora-image:44}
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out=$(readlink -f "$here/out" 2>/dev/null || true)
[ -d "$out" ] || { echo "image-container: $here/out is not a directory or link" >&2; exit 1; }

cmd=${1:-}
[ $# -gt 0 ] && shift

case "$cmd" in
build)
	exec docker build --pull=false -t "$IMAGE" -f "$here/image/Containerfile" "$here/image"
	;;
run | shell)
	docker image inspect "$IMAGE" >/dev/null 2>&1 || {
		echo "image-container: $IMAGE missing, run: $0 build" >&2
		exit 1
	}
	tty=()
	[ -t 0 ] && [ -t 1 ] && tty=(-t)
	args=(--rm -i "${tty[@]}" --privileged
		-v "$here:/sp11" -v "$out:/out" -e SP11_OUT=/out
		-e "SP11_UID=$(id -u)" -e "SP11_GID=$(id -g)"
		--tmpfs /tmp:exec,size=4g
		-e "SP11_IMAGE_ID=$(docker image inspect -f '{{.Id}}' "$IMAGE")"
		-w /sp11)
	# private L0 only (scripts/image-test-static.sh sets SP11_MOUNT_MAC_CONF=1 for a *-private ISO): the
	# operator's address file, read-only, so L0 can compare hashes. Builds never get it (the host stages).
	if [ "${SP11_MOUNT_MAC_CONF:-0}" = 1 ]; then
		macconf=${SP11_MAC_CONF:-$HOME/sp11-windows-dumps/live-inventory/sp11-mac.conf}
		[ -r "$macconf" ] || macconf=$here/sources/windows/live-inventory/sp11-mac.conf
		macconf=$(readlink -f "$macconf")
		[ -r "$macconf" ] || { echo "image-container: private L0 needs the address file (SP11_MAC_CONF)" >&2; exit 1; }
		args+=(-v "$macconf:/run/sp11-private/sp11-mac.conf:ro" -e SP11_MAC_CONF_IN=/run/sp11-private/sp11-mac.conf)
	fi
	# optional memory cap (the ISO build must not starve a running kernel build)
	[ -n "${SP11_DOCKER_MEMORY:-}" ] && args+=(--memory "$SP11_DOCKER_MEMORY" --memory-swap "$SP11_DOCKER_MEMORY")
	# the ISO build work directory is large; keep it on the disk, not in RAM
	mkdir -p "$out/image-work"
	[ "$cmd" = shell ] && set -- bash
	[ $# -gt 0 ] || { echo "usage: $0 run CMD [ARGS]" >&2; exit 1; }
	rc=0
	docker run "${args[@]}" "$IMAGE" "$@" || rc=$?
	# the container runs as root: give our outputs back to the invoking user
	docker run --rm -v "$out:/out" "$IMAGE" bash -c \
		"for d in iso image-work repo; do [ -e /out/\$d ] && chown -R $(id -u):$(id -g) /out/\$d; done; true" >/dev/null 2>&1 || true
	exit "$rc"
	;;
*)
	echo "usage: $0 build | run CMD [ARGS] | shell" >&2
	exit 1
	;;
esac
