#!/usr/bin/env bash
# Container side of the kiwi ISO build (decision D16). Run by scripts/image-build.sh, not directly.
#
# Fedora's own description (pagure.io/fedora-kiwi-descriptions, branch f44, commit pinned in
# image/kiwi/DESCRIPTION_COMMIT), profile Workstation-Live, built the way Fedora's CI builds it:
# the repository's own `kiwi-build` wrapper (tmt/tests/build-image.fmf), which calls
#   kiwi-ng --type=iso --profile=Workstation-Live --kiwi-file=Fedora.kiwi system build \
#           --description DIR --target-dir DIR-build  <ISO volid/application id from Fedora's generator>
# On top of it only the SP11 layer of image/README.md ("kiwi layer"):
#   image/kiwi/patches/*.patch   two patches of Fedora files (include our layer, verbose cmdline)
#   image/kiwi/overlay/          sp11.xml, GRUB template, root files (dracut, SELinux, collector conf)
#   image/overlay/               log collector and its unit (shared with the lmc build)
#   out/firmware-root            DriverStore firmware, copied into the root overlay
#   out/rpms -> out/repo         our kernel RPMs, local repository with priority over Fedora's
set -euo pipefail

OUT=${SP11_OUT:-/out}
REPO=/sp11
name_arg=${1:-}
id=$(date -u +%Y%m%dT%H%M%SZ)
name=${name_arg:-sp11-fedora44-aarch64-kiwi-$id}
work=$OUT/image-work/$id
isodir=$OUT/iso
mkdir -p "$work/tmp" "$isodir" "$OUT/kiwi"
cd "$work"   # /sp11 is a worktree whose .git file points outside the container
log() { echo "image-build[kiwi]: $*" >&2; }

# ---- 1. Fedora's description at the pinned commit
pin=$(tr -d '[:space:]' <"$REPO/image/kiwi/DESCRIPTION_COMMIT")
src=$OUT/kiwi/fedora-kiwi-descriptions.git
url=https://pagure.io/fedora-kiwi-descriptions.git
head=$(git ls-remote "$url" refs/heads/f44 | cut -f1)
[ -n "$head" ] || { log "cannot read branch f44 of $url"; exit 1; }
if [ -d "$src" ]; then git -C "$src" fetch -q origin "+refs/heads/f44:refs/heads/f44" || log "WARNING: fetch failed, using the cached clone"; else git clone -q --bare -b f44 "$url" "$src"; fi
log "description pin $pin, branch f44 head $head$([ "$pin" = "$head" ] && echo ' (same)' || echo ' (DIFFERENT: the pin is kept)')"
git -C "$src" cat-file -e "$pin^{commit}" || { log "pinned commit not in the clone"; exit 1; }
desc=$work/description
mkdir -p "$desc"
git -C "$src" archive "$pin" | tar -x -C "$desc"
cd "$desc"

# ---- 2. SP11 layer: patches of Fedora files (fail loudly when the pin drifts), overlay, firmware
for p in "$REPO"/image/kiwi/patches/*.patch; do
	log "patch $(basename "$p")"
	patch -p1 --no-backup-if-mismatch -s <"$p"
done
cp -a "$REPO/image/overlay/." "$desc/root/"
rm -f "$desc/root/etc/default/grub" "$desc/root/etc/sp11-log-collector.conf"   # lmc-only; the kiwi overlay has its own
cp -a "$REPO/image/kiwi/overlay/root/." "$desc/root/"
cp -a "$REPO/image/kiwi/overlay/sp11.xml" "$REPO/image/kiwi/overlay/grub-arm.cfg.iso-template" "$desc/"
chmod 0755 "$desc/root/usr/libexec/sp11-log-collector"
mkdir -p "$desc/root/etc/systemd/system/multi-user.target.wants"
# Plymouth is installed (required by Fedora's package groups) but switched off: units masked
for u in start quit quit-wait read-write switch-root halt reboot poweroff kexec; do
	ln -sf /dev/null "$desc/root/etc/systemd/system/plymouth-$u.service"
done
ln -sf /usr/lib/systemd/system/sp11-log-collector.service "$desc/root/etc/systemd/system/multi-user.target.wants/sp11-log-collector.service"

[ -d "$OUT/firmware-root/lib/firmware" ] || { log "$OUT/firmware-root missing; run scripts/firmware-stage.sh"; exit 1; }
mkdir -p "$desc/root/usr/lib/firmware"
cp -a "$OUT/firmware-root/lib/firmware/." "$desc/root/usr/lib/firmware/"
rm -f "$OUT/image-work/firmware-installed.sha256"
( cd "$OUT/firmware-root/lib/firmware" && find . -type f | sort | xargs sha256sum ) >"$OUT/image-work/firmware-installed.sha256"

# ---- 3. local repository with our kernel RPMs (no debuginfo, devel, uki)
log "local repository from $OUT/rpms"
rm -rf "$OUT/repo"
mkdir -p "$OUT/repo"
for n in kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra; do
	f=$(ls "$OUT"/rpms/"$n"-[0-9]*.aarch64.rpm 2>/dev/null | head -n1) || true
	[ -n "$f" ] || { log "no $n RPM in $OUT/rpms"; exit 1; }
	cp "$f" "$OUT/repo/"
done
createrepo_c -q "$OUT/repo"
kcore=$(ls "$OUT"/repo/kernel-core-*.rpm)
kver=$(rpm -qp --qf '%{version}-%{release}.%{arch}' "$kcore")
echo "kernel-core-$kver" >"$OUT/image-work/kernel-nevra.txt"

# ---- 4. DTB on the ISO root (config-cdroot.tar of kiwi, unpacked into the ISO tree)
dtbtmp=$work/dtb
mkdir -p "$dtbtmp/boot/dtb/qcom"
rpm2cpio "$kcore" | cpio -i --quiet --to-stdout "./lib/modules/$kver/dtb/qcom/x1p64100-microsoft-denali.dtb" \
	>"$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb"
[ -s "$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb" ] || { log "DTB not in $kcore"; exit 1; }
tar -C "$dtbtmp" -cf "$desc/config-cdroot.tar" boot

# ---- 5. pins for the build record
dnf -q repoinfo fedora updates --setopt=reposdir=/etc/yum.repos.d 2>/dev/null |
	grep -E '^(Repo-id|Repo-revision|Repo-updated)' >"$work/repos.txt" || true

# ---- 6. kiwi, through Fedora's own wrapper
log "kiwi-ng via kiwi-build, log: $work/kiwi.log (several tens of minutes)"
start=$(date +%s)
set +e
./kiwi-build --debug --image-type=iso --image-profile=Workstation-Live --kiwi-file=Fedora.kiwi \
	--kiwi-description-dir="$desc" --output-dir="$work/out" >"$work/kiwi.log" 2>&1
rc=$?
set -e
tail -n 25 "$work/kiwi.log" | cut -c1-300
[ "$rc" = 0 ] || { log "kiwi failed (rc=$rc), see $work/kiwi.log"; exit 1; }
elapsed=$(($(date +%s) - start))
iso=$(ls "$work"/out-build/*.iso 2>/dev/null | head -n1)
[ -f "$iso" ] || { log "no ISO in $work/out-build"; ls -la "$work/out-build" >&2; exit 1; }
log "ISO $iso after ${elapsed}s"
echo "$id $name $elapsed $iso" >"$work/kiwi-result.txt"
