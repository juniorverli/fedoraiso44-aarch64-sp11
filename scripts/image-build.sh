#!/usr/bin/env bash
# Build the SP11 Fedora 44 live ISO with livemedia-creator --no-virt (decision D11).
#
#   scripts/image-build.sh [--builder kiwi|lmc] [--smoke] [--private] [--name NAME] [--mem GiB]
#
# --private (or SP11_PRIVATE=1): private build for the operator's own device, kiwi only. Embeds the
# Windows-derived Wi-Fi/Bluetooth settings (image/README.md, "Private build mode"): /etc/sp11/bt-address,
# a persistent Wi-Fi address and the derived ath12k board file. Inputs: SP11_MAC_CONF (default
# ~/sp11-windows-dumps/live-inventory/sp11-mac.conf) and SP11_WIFI_BOARD2 (default
# out/firmware-private/wifi/ath12k/WCN7850/hw2.0/board-2.bin). The ISO name carries "-private";
# the ISO must never be shared. Default is the public build: no address, no derived blob.
#
# --builder kiwi (default, decision D16): kiwi-ng with Fedora's f44 Workstation-Live description,
# scripts/image-build-kiwi.sh. --builder lmc: the livemedia-creator path of M2 (D11), kept until
# the kiwi ISO passes L0 and L1. With kiwi, --smoke only allows a missing DTB variant (D19): a copy of
# the packaged DTB stands in, the ISO is named ...-kiwi-smoke-..., the record says
# "dtb_variants_smoke_copy": true, and it never goes to the device. The kiwi build also refuses a
# kernel-core not newer than image/kiwi/MIN_KERNEL_EXCLUSIVE.
#
# Default (M2 build): needs the kernel RPMs in out/rpms/ and the staged firmware in
# out/firmware-root/ (scripts/firmware-stage.sh). --smoke uses Fedora's own kernel and no
# firmware, only to exercise the pipeline and the tests; its DTB check is relaxed through
# SP11_DTB and the record says "smoke": true. A smoke ISO never goes to the device.
#
# Refuses to start while out/.kernel-build.lock is held (a BTF kernel build needs the RAM).
# Runs inside the container of scripts/image-container.sh (re-executes itself there).
# Output: out/iso/<name>.iso, out/iso/<name>.json (build record), out/iso/<name>.iso.sha256.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

smoke=0 name= mem= inside=0 builder=kiwi
private=0
[ "${SP11_PRIVATE:-0}" = 1 ] && private=1
while [ $# -gt 0 ]; do
	case $1 in
	--builder) builder=${2:?}; shift ;;
	--smoke) smoke=1 ;;
	--private) private=1 ;;
	--name) name=${2:?}; shift ;;
	--mem) mem=${2:?}; shift ;;
	--inside) inside=1 ;;
	*) echo "usage: $0 [--builder kiwi|lmc] [--smoke] [--private] [--name NAME] [--mem GiB]" >&2; exit 2 ;;
	esac
	shift
done

case $builder in kiwi | lmc) ;; *) echo "image-build: --builder must be kiwi or lmc" >&2; exit 2 ;; esac
[ "$private" = 0 ] || [ "$builder" = kiwi ] || { echo "image-build: --private needs --builder kiwi" >&2; exit 2; }
# mkfs.erofs of the kiwi live root needs about 3 GiB of its own on top of the build (OOM at 6 GiB)
[ -n "$mem" ] || { [ "$builder" = kiwi ] && mem=9 || mem=6; }

# ------------------------------------------------------------------ host ----
if [ "$inside" = 0 ]; then
	out=$(readlink -f "$here/out")
	if ! flock -n "$out/.kernel-build.lock" true 2>/dev/null; then
		echo "image-build: $out/.kernel-build.lock is held (kernel build running); not starting the ISO build" >&2
		exit 3
	fi
	# disk guard: the real limit is the Windows drive under the WSL2 VHDX, not `df /`
	# shellcheck source=kernel-common.sh
	. "$here/scripts/kernel-common.sh"
	read -r h src < <(kernel_headroom)
	min=${SP11_MIN_HEADROOM_GIB:-30}
	echo "image-build: disk headroom $((h / KERNEL_GIB)) GiB [$src], need >= $min GiB"
	if ((h < min * KERNEL_GIB)); then
		echo "image-build: REFUSED: headroom $((h / KERNEL_GIB)) GiB < $min GiB [$src]" >&2
		exit 4
	fi
	if [ "$smoke" = 0 ]; then
		ls "$out"/rpms/kernel-core-*.rpm >/dev/null 2>&1 || { echo "image-build: no kernel-core RPM in $out/rpms/" >&2; exit 1; }
		[ -d "$out/firmware-root/lib/firmware" ] || { echo "image-build: $out/firmware-root missing; run scripts/firmware-stage.sh" >&2; exit 1; }
	fi
	if [ "$builder" = kiwi ]; then
		ls "$out"/rpms/kernel-core-*.rpm >/dev/null 2>&1 || { echo "image-build: no kernel-core RPM in $out/rpms/" >&2; exit 1; }
		[ -d "$out/firmware-root/lib/firmware" ] || { echo "image-build: $out/firmware-root missing; run scripts/firmware-stage.sh" >&2; exit 1; }
		for v in m11 m11-notouch m11-audio; do
			for ext in dtb json; do
				[ -s "$out/dtb-variants/7.3.0-65.sp11.8.fc44.aarch64/qcom/x1p64100-microsoft-denali-$v.$ext" ] || {
					echo "image-build: REFUSED: kernel worker has not published the M11 $v $ext" >&2; exit 6;
				}
			done
		done
		kargs=()
		[ "$smoke" = 1 ] && kargs+=(--smoke)
		if [ "$private" = 1 ]; then
			# Private inputs are read here, on the host, by image/tools/private-stage.py (values never
			# printed). The staging tree lives in the git-ignored out/ and is removed by the container side.
			macconf=${SP11_MAC_CONF:-$HOME/sp11-windows-dumps/live-inventory/sp11-mac.conf}
			[ -r "$macconf" ] || macconf=$here/sources/windows/live-inventory/sp11-mac.conf
			board_args=()
			if [ -n "${SP11_WIFI_BOARD2:-}" ]; then
				board_args=(--board "$SP11_WIFI_BOARD2" --fedora "${SP11_WIFI_FEDORA_BOARD2:-$out/image-inputs/wifi/fedora-board-2.bin.xz}")
				[ -n "${SP11_WIFI_BOARD2_SHA256:-}" ] && board_args+=(--board-sha256 "$SP11_WIFI_BOARD2_SHA256")
			fi
			# scrub on every exit path, including Ctrl-C/SIGTERM/SIGHUP while the container runs, a failed
			# stage, and a container killed without running its own trap
			trap 'rm -rf "$out/private-stage"' EXIT
			trap 'exit 130' INT
			trap 'exit 143' TERM
			trap 'exit 129' HUP
			echo "image-build: PRIVATE build: embeds device addresses; never share the ISO"
			python3 -I "$here/image/tools/private-stage.py" stage --mac-conf "$macconf" "${board_args[@]}" --out "$out/private-stage" || exit 6
			kargs+=(--private)
		fi
		[ -n "$name" ] && kargs+=("$name")
		if [ "$private" = 1 ]; then
			# no exec: the staged values must be removed even when the container side fails early
			rc=0
			SP11_DOCKER_MEMORY="${mem}g" "$here/scripts/image-container.sh" run /sp11/scripts/image-build-kiwi.sh "${kargs[@]}" || rc=$?
			rm -rf "$out/private-stage"
			exit "$rc"
		fi
		SP11_DOCKER_MEMORY="${mem}g" exec "$here/scripts/image-container.sh" run /sp11/scripts/image-build-kiwi.sh "${kargs[@]}"
	fi
	# the container gets a memory cap so a running kernel build keeps its RAM
	args=("--inside")
	[ "$smoke" = 1 ] && args+=(--smoke)
	[ -n "$name" ] && args+=(--name "$name")
	SP11_DOCKER_MEMORY="${mem}g" exec "$here/scripts/image-container.sh" run /sp11/scripts/image-build.sh "${args[@]}"
fi

# ------------------------------------------------------------- container ----
OUT=${SP11_OUT:-/out}
REPO=/sp11
id=$(date -u +%Y%m%dT%H%M%SZ)
kind=m2
[ "$smoke" = 1 ] && kind=smoke
name=${name:-sp11-fedora44-aarch64-$kind-$id}
work=$OUT/image-work/$id
isodir=$OUT/iso
mkdir -p "$work" "$isodir"
log() { echo "image-build: $*" >&2; }

# 1. local repository for our kernel RPMs
if [ "$smoke" = 0 ]; then
	log "local repository from $OUT/rpms"
	rm -rf "$OUT/repo"
	mkdir -p "$OUT/repo"
	find "$OUT/rpms" -maxdepth 1 -name '*.rpm' ! -name '*.src.rpm' ! -name '*debuginfo*' ! -name '*debugsource*' \
		-exec cp -l {} "$OUT/repo/" \; 2>/dev/null ||
		find "$OUT/rpms" -maxdepth 1 -name '*.rpm' ! -name '*.src.rpm' ! -name '*debuginfo*' ! -name '*debugsource*' \
			-exec cp {} "$OUT/repo/" \;
	createrepo_c -q "$OUT/repo"
	kernel_repo='repo --name=sp11-local --baseurl=file:///out/repo --cost=10'
	exclude='--excludepkgs=kernel,kernel-core,kernel-modules,kernel-modules-core,kernel-modules-extra,kernel-modules-internal,kernel-devel,kernel-devel-matched,kernel-uki-virt,kernel-debug,kernel-debug-core,kernel-debug-modules,kernel-debug-modules-core,kernel-debug-modules-extra,kernel-debug-devel'
	require_fw=1
else
	kernel_repo=
	exclude=
	require_fw=0
	# a Fedora kernel does not carry the SP11 DTB; use a DTB that kernel has
	export SP11_DTB=${SP11_DTB:-qcom/x1e80100-crd.dtb}
fi

# 2. resolve the kickstart placeholders
ks=$work/sp11-live.resolved.ks
sed -e "s|@SP11_KERNEL_REPO@|$kernel_repo|" \
	-e "s|@SP11_EXCLUDE_KERNEL@|$exclude|g" \
	-e "s|@SP11_REQUIRE_FIRMWARE@|$require_fw|" \
	"$REPO/image/sp11-live.ks" >"$ks"
ksvalidator "$ks" >"$work/ksvalidator.txt" 2>&1 || { cat "$work/ksvalidator.txt" >&2; log "kickstart is invalid"; exit 1; }

# 3. pins for the build record: repository metadata revisions and container image
dnf -q repoinfo fedora updates --setopt=reposdir=/etc/yum.repos.d 2>/dev/null |
	grep -E '^(Repo-id|Repo-revision|Repo-updated)' >"$work/repos.txt" || true
rm -f "$OUT/image-work/packages.txt" "$OUT/image-work/kernel-nevra.txt" "$OUT/image-work/firmware-installed.sha256"

# 4. livemedia-creator
log "livemedia-creator, log: $work/lmc.log (several tens of minutes)"
mkdir -p "$work/tmp"
start=$(date +%s)
livemedia-creator --no-virt --make-iso --nomacboot --iso-only --iso-name "$name.iso" \
	--ks "$ks" \
	--lorax-templates "$REPO/image/lorax-templates" \
	--project Fedora --releasever 44 --release "SP11 $kind $id" \
	--volid SP11-Fedora-44 \
	--compression zstd --compress-arg "-Xcompression-level 15" \
	--tmp "$work/tmp" --resultdir "$work/result" \
	--logfile "$work/lmc.log" 2>&1 | tail -n 40 || true
iso=$work/result/$name.iso
[ -f "$iso" ] || { log "no ISO produced, see $work/lmc.log and $work/tmp/*.log"; exit 1; }
elapsed=$(($(date +%s) - start))

# 5. verbose check, as the task demands: no quiet/rhgb in any grub.cfg of the ISO or its EFI image
log "grep check: quiet/rhgb in grub.cfg"
chk=$work/grubcheck
mkdir -p "$chk"
xorriso -osirrox on -indev "$iso" -extract /EFI/BOOT/grub.cfg "$chk/iso-grub.cfg" >/dev/null 2>&1
xorriso -osirrox on -indev "$iso" -extract /images/efiboot.img "$chk/efiboot.img" >/dev/null 2>&1
mcopy -i "$chk/efiboot.img" ::EFI/BOOT/grub.cfg "$chk/esp-grub.cfg"
for f in "$chk/iso-grub.cfg" "$chk/esp-grub.cfg"; do
	if grep -v '^[[:space:]]*#' "$f" | grep -w -E 'quiet|rhgb|splash' >/dev/null; then
		log "FAIL: quiet/rhgb/splash in $f"
		exit 1
	fi
done

# 6. publish
mv -f "$iso" "$isodir/$name.iso"
( cd "$isodir" && sha256sum "$name.iso" >"$name.iso.sha256" )
sha=$(cut -d' ' -f1 "$isodir/$name.iso.sha256")

# 7. build record
python3 - "$isodir/$name.json" "$name" "$sha" "$kind" "$id" "$elapsed" "$work" "$REPO" "$OUT" <<'EOF'
import hashlib, json, os, re, subprocess, sys
rec, name, sha, kind, bid, elapsed, work, repo, out = sys.argv[1:10]

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def read(p, default=''):
    try:
        return open(p).read()
    except OSError:
        return default

pk = [l for l in read(f"{out}/image-work/packages.txt").splitlines() if l]
fw = [l.split() for l in read(f"{out}/image-work/firmware-installed.sha256").splitlines() if l]
cmdline = {}
cfg = read(f"{work}/grubcheck/esp-grub.cfg")
common = re.search(r'set sp11_common="([^"]*)"', cfg)
entries = []
for m in re.finditer(r"menuentry '([^']*)'.*?\{(.*?)\}", cfg, re.S):
    lin = re.search(r"^\s*linux \S+ \$sp11_common(.*)$", m.group(2), re.M)
    entries.append({"title": m.group(1), "extra_args": lin.group(1).strip() if lin else None,
                    "devicetree": bool(re.search(r"^\s*devicetree ", m.group(2), re.M))})
series = f"{repo}/kernel/series"
manifest = f"{repo}/firmware/manifest.toml"
record = {
    "name": name, "kind": kind, "smoke": kind == "smoke", "build_id": bid,
    "iso_sha256": sha, "iso_size": os.path.getsize(f"{out}/iso/{name}.iso"),
    "build_seconds": int(elapsed),
    "kernel_nevra": read(f"{out}/image-work/kernel-nevra.txt").strip(),
    "kernel_series_sha256": sha256(series) if os.path.exists(series) else None,
    "firmware_manifest_sha256": sha256(manifest) if os.path.exists(manifest) else None,
    "firmware_installed": [{"sha256": a, "path": b} for a, b in fw],
    "firmware_installed_listing_sha256": hashlib.sha256("\n".join(" ".join(x) for x in fw).encode()).hexdigest(),
    "dtb": os.environ.get("SP11_DTB", "qcom/x1p64100-microsoft-denali.dtb"),
    "kernel_cmdline_common": common.group(1) if common else None,
    "kernel_cmdline_reasons": "image/README.md, GRUB 2 and the kernel command line",
    "grub_entries": entries,
    "repos": read(f"{work}/repos.txt").strip().splitlines(),
    "container_image": os.environ.get("SP11_IMAGE_ID", ""),
    "package_count": len(pk), "packages": pk,
    "tools": {t: subprocess.run(["rpm", "-q", t], capture_output=True, text=True).stdout.strip()
              for t in ("lorax", "anaconda", "grub2-efi-aa64", "shim-aa64", "dracut", "xorriso")},
}
json.dump(record, open(rec, "w"), indent=1)
EOF
log "done: $isodir/$name.iso ($sha)"
log "record: $isodir/$name.json"
