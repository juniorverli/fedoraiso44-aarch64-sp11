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
name_arg= post_only= smoke=0 private=0
while [ $# -gt 0 ]; do
	case $1 in
	--post-only) post_only=${2:?build id}; shift ;;   # redo steps 6b-9 of a finished kiwi run
	--private) private=1 ;;   # operator-only build: stage from out/private-stage (image/README.md)
	--smoke) smoke=1 ;;   # D19: a missing DTB variant is replaced by a copy of the packaged DTB (pipeline test only)
	*) name_arg=$1 ;;
	esac
	shift
done

id=${post_only:-$(date -u +%Y%m%dT%H%M%SZ)}
kind=kiwi; [ "$smoke" = 1 ] && kind=kiwi-smoke
name=${name_arg:-sp11-fedora44-aarch64-$kind-$id}
if [ "$private" = 1 ]; then
	case $name in *-private*) ;; *) name=$name-private ;; esac
fi
work=$OUT/image-work/$id
isodir=$OUT/iso
mkdir -p "$work/tmp" "$isodir" "$OUT/kiwi"
cd "$work"   # /sp11 is a worktree whose .git file points outside the container
log() { echo "image-build[kiwi]: $*" >&2; }
# private mode: whatever happens, the staged values and the copies in the work tree are removed
scrub_private() {
	rm -rf "$OUT/private-stage"
	rm -f "$work/description/root/etc/sp11/bt-address" "$work/description/root/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf" \
		"$work/description/root/etc/systemd/network/10-sp11-wifi.link" \
		"$work/description/root/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin"
}
[ "$private" = 1 ] && trap scrub_private EXIT

# The local Fedora-native iptsd RPM must be prepared before the single compose.
iptsd_rpm=$OUT/rpms/iptsd-3.1.0-1.fc44.aarch64.rpm
iptsd_record=${iptsd_rpm%.rpm}.json
[ -s "$iptsd_rpm" ] && [ -s "$iptsd_record" ] &&
[ "$(sha256sum "$iptsd_rpm" | cut -d' ' -f1)" = "$(jq -r .rpm_sha256 "$iptsd_record")" ] &&
[ "$(sha256sum "$REPO/image/iptsd/iptsd.spec" | cut -d' ' -f1)" = "$(jq -r .local_spec_sha256 "$iptsd_record")" ] || {
	log "REFUSED: build the pinned Fedora-native iptsd RPM with scripts/image-build-iptsd.sh first"; exit 6;
}

if [ -z "$post_only" ]; then
# ---- 0. the kernel RPMs. Only the top level of out/rpms counts (older builds live in out/rpms/archive/):
# exactly one kernel NEVRA may sit there, and it must be newer than the last kernel that is known not
# to carry the M3 display patches (image/kiwi/MIN_KERNEL_EXCLUSIVE, D19). All five RPMs of the image
# come from that one build.
nevras=$(for f in "$OUT"/rpms/kernel*-[0-9]*.rpm; do
	[ -e "$f" ] || continue
	case $f in *.src.rpm) continue ;; esac
	rpm -qp --qf '%{version}-%{release}.%{arch}\n' "$f"
done | sort -u)
[ -n "$nevras" ] || { log "no kernel RPM in $OUT/rpms"; exit 1; }
if [ "$(echo "$nevras" | wc -l)" -gt 1 ]; then
	log "REFUSED: more than one kernel NEVRA at the top level of $OUT/rpms (older ones belong in $OUT/rpms/archive/):"
	echo "$nevras" | sed 's/^/    /' >&2
	exit 5
fi
kver_full=$nevras
kcore_src=$OUT/rpms/kernel-core-$kver_full.rpm
[ -f "$kcore_src" ] || { log "no kernel-core-$kver_full.rpm in $OUT/rpms"; exit 1; }
newest_vr=${kver_full%.*}
min=$(tr -d '[:space:]' <"$REPO/image/kiwi/MIN_KERNEL_EXCLUSIVE")
if [ "$(rpm --eval "%{lua:print(rpm.vercmp('$newest_vr', '$min'))}")" -le 0 ]; then
	log "REFUSED: kernel $newest_vr is not newer than $min; the M3 image needs the build with the display patches (D19)"
	exit 5
fi
log "kernel $kver_full (newer than $min, the only kernel NEVRA at the top level of out/rpms)"

# M10 requires revision-7 RPMs and both atomically published DTB/JSON pairs.
[ "$kver_full" = 7.3.0-65.sp11.7.fc44.aarch64 ] || {
	log "REFUSED: M10 requires kernel 7.3.0-65.sp11.7.fc44.aarch64, found $kver_full"; exit 6;
}
patch_series_sha=$( . "$REPO/scripts/kernel-common.sh"; kernel_series_hash )
for v in m10 m10-notouch; do
	vsrc=$OUT/dtb-variants/$kver_full/qcom/x1p64100-microsoft-denali-$v
	[ -s "$vsrc.dtb" ] && [ -s "$vsrc.json" ] || {
		log "REFUSED: $v DTB and JSON not yet published by the kernel worker"; exit 6;
	}
	[ "$(sha256sum "$vsrc.dtb" | cut -d' ' -f1)" = "$(jq -r .sha256 "$vsrc.json")" ] &&
	[ "$(jq -r .kver "$vsrc.json")" = "$kver_full" ] &&
	[ "$(jq -r .series_rev "$vsrc.json")" = 7 ] &&
	[ "$(jq -r .series_hash_sha256 "$vsrc.json")" = "$patch_series_sha" ] || {
		log "REFUSED: $v DTB hash/release/series differs from the kernel worker JSON"; exit 6;
	}
done

# ---- 1. Fedora's description at the pinned commit
pin=$(tr -d '[:space:]' <"$REPO/image/kiwi/DESCRIPTION_COMMIT")
src=$OUT/kiwi/fedora-kiwi-descriptions.git
url=https://pagure.io/fedora-kiwi-descriptions.git
head=$(git ls-remote "$url" refs/heads/f44 | cut -f1)
[ -n "$head" ] || { log "cannot read branch f44 of $url"; exit 1; }
[ -d "$src" ] || { log "cached description $src missing; request it from the sources owner (no git writes)"; exit 1; }
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
rm -f "$desc/root/etc/sp11-log-collector.conf"   # lmc-only; the kiwi overlay has its own (ESP label BOOT)
cp -a "$REPO/image/kiwi/overlay/root/." "$desc/root/"
cp -a "$REPO/image/kiwi/overlay/sp11.xml" "$REPO/image/kiwi/overlay/grub-arm.cfg.iso-template" "$desc/"
chmod 0755 "$desc/root/usr/libexec/sp11-log-collector"
chmod 0755 "$desc/root/usr/libexec/sp11-touch-userspace-collect"
# D19 / display-lcd request: the DPCD reader of the display worker, shipped unchanged and run by the
# collector as root against every /dev/drm_dp_aux*
cp "$REPO/hardware/display-lcd/tools/collect-dpcd.py" "$desc/root/usr/libexec/sp11-collect-dpcd.py"
chmod 0755 "$desc/root/usr/libexec/sp11-collect-dpcd.py"
# Touch owner section 8: stage the stdout-only helper unchanged.
install -m 0755 "$REPO/hardware/touch-pen/collect-read-only.sh" "$desc/root/usr/libexec/sp11-touch-pen-collect"
# Component collector requests (R-I1 and Wi-Fi I1/I2), copied unchanged from the merged dossiers.
mkdir -p "$desc/root/etc/sp11-log-collector.d"
for c in dsp-subsystems wifi; do
	cp "$REPO/hardware/$c/collector/$c.sh" "$desc/root/etc/sp11-log-collector.d/$c.sh"
done
# M10: the owner's DSP collector plus the image-owned sp11-glink/remoteproc append (one drop-in, one output file)
cat "$REPO/hardware/dsp-subsystems/collector/dsp-subsystems.sh" "$REPO/image/component-inputs/dsp-glink-append.sh" \
	>"$desc/root/etc/sp11-log-collector.d/dsp-subsystems.sh"
cp "$REPO/hardware/wifi/collector/wifi-unblock-probe.sh" "$desc/root/usr/libexec/sp11-wifi-unblock-probe.sh"
# D24: read-only snapshots taken with git show main:<path>, pinned in sources.json.
# Public build: no operator address input is read or staged. Private mode: see below.
inputs=$REPO/image/component-inputs
install -m 0755 "$inputs/bluetooth/userspace/sp11-bt-address" "$desc/root/usr/libexec/sp11-bt-address"
install -m 0755 "$inputs/bluetooth/userspace/sp11-bt-collect" "$desc/root/usr/libexec/sp11-bt-collect"
install -m 0644 "$inputs/bluetooth/userspace/sp11-bt-address.service" "$desc/root/usr/lib/systemd/system/sp11-bt-address.service"
mkdir -p "$desc/root/usr/libexec/sp11/ec-sam" "$desc/root/etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants"
for tool in collect-input-capabilities.sh collect-power.sh ssam-ro.py; do
	install -m 0755 "$inputs/ec-sam/tools/$tool" "$desc/root/usr/libexec/sp11/ec-sam/$tool"
done
ln -sf /usr/lib/systemd/system/sp11-bt-address.service "$desc/root/etc/systemd/system/sys-subsystem-bluetooth-devices-hci0.device.wants/sp11-bt-address.service"
mkdir -p "$desc/root/etc/systemd/system/multi-user.target.wants"
# Plymouth is installed (required by Fedora's package groups) but switched off: units masked
for u in start quit quit-wait read-write switch-root halt reboot poweroff kexec; do
	ln -sf /dev/null "$desc/root/etc/systemd/system/plymouth-$u.service"
done
for u in sp11-log-collector.service sp11-log-collector-session-first.path sp11-log-collector-session-user.path sp11-rfkill-events.service; do
	ln -sf "/usr/lib/systemd/system/$u" "$desc/root/etc/systemd/system/multi-user.target.wants/$u"
done

# Private mode (operator device only): copy the staged tree made by the host side. It holds the
# Bluetooth address file, the Wi-Fi address (NetworkManager conf and .link) and the derived board file.
if [ "$private" = 1 ]; then
	ps=$OUT/private-stage
	[ -s "$ps/private-record.json" ] && [ -d "$ps/root" ] || { log "REFUSED: private stage missing; run scripts/image-build.sh --private"; exit 6; }
	cp -a "$ps/root/." "$desc/root/"
	chown -R 0:0 "$desc/root/etc/sp11" "$desc/root/usr/lib/firmware/updates"
	chown 0:0 "$desc/root/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf" "$desc/root/etc/systemd/network/10-sp11-wifi.link"
	cp "$ps/private-record.json" "$work/private-record.json"   # hash prefixes only
	log "PRIVATE build: staged device settings copied into the root (values not logged)"
fi

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
	f=$OUT/rpms/$n-$kver_full.rpm
	[ -f "$f" ] || { log "no $n-$kver_full.rpm in $OUT/rpms"; exit 1; }
	cp "$f" "$OUT/repo/"
done
cp "$iptsd_rpm" "$OUT/repo/"
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
# M10: the kernel worker variants next to the packaged DTB. The build fails without
# it; with --smoke a copy of the packaged DTB stands in (recorded, never for the device).
variants_smoke_copy=0
for v in m10 m10-notouch; do
	vf=x1p64100-microsoft-denali-$v.dtb
	vsrc=$OUT/dtb-variants/$kver/qcom/$vf
	if [ -s "$vsrc" ]; then
		cp "$vsrc" "$dtbtmp/boot/dtb/qcom/$vf"
		mkdir -p "$work/dtb-records"
		for r in "${vsrc%.dtb}.json" "$vsrc.json"; do [ -f "$r" ] && cp "$r" "$work/dtb-records/$vf.json"; done
	elif [ "$smoke" = 1 ]; then
		log "SMOKE: $vsrc missing, using a copy of the packaged DTB for the $v entry"
		cp "$dtbtmp/boot/dtb/qcom/x1p64100-microsoft-denali.dtb" "$dtbtmp/boot/dtb/qcom/$vf"
		variants_smoke_copy=1
	else
		log "REFUSED: DTB variant $vsrc is missing (the kernel worker writes it); --smoke only for a pipeline test"
		exit 6
	fi
done
tar -C "$dtbtmp" -cf "$desc/config-cdroot.tar" boot

# ---- 5. pins for the build record
dnf -q repoinfo fedora updates --setopt=reposdir=/etc/yum.repos.d 2>/dev/null |
	grep -E '^(Repo-id|Repo-revision|Repo-updated)' >"$work/repos.txt" || true
printf "pin=%s\nhead=%s\nkver=%s\nvariants_smoke_copy=%s\n" "$pin" "$head" "$kver" "$variants_smoke_copy" >"$work/build-vars.env"
# ---- 6. kiwi, through Fedora's own wrapper
# The image root must not be built below /out: /out is a bind mount of a host path, kernel-install
# computes the BLS entry paths from the mount's source (/proc/self/mountinfo) and wrote the host path
# (with the user name) into /boot/loader/entries/*.conf of the first kiwi ISO (L0 check 7.2). The
# container's own file system has root "/", so the paths stay clean. Results are copied to $work.
kiwiout=/var/tmp/sp11-kiwi
rm -rf "$kiwiout"; mkdir -p "$kiwiout"
log "kiwi-ng via kiwi-build, log: $work/kiwi.log (several tens of minutes)"
start=$(date +%s)
set +e
./kiwi-build --debug --image-type=iso --image-profile=Workstation-Live --kiwi-file=Fedora.kiwi \
	--kiwi-description-dir="$desc" --output-dir="$kiwiout/out" >"$work/kiwi.log" 2>&1
rc=$?
set -e
tail -n 25 "$work/kiwi.log" | cut -c1-300
[ "$rc" = 0 ] || { log "kiwi failed (rc=$rc), see $work/kiwi.log"; exit 1; }
elapsed=$(($(date +%s) - start))
mkdir -p "$work/out-build"
cp "$kiwiout"/out-build/Fedora.aarch64-44.* "$kiwiout"/out-build/kiwi.result* "$work/out-build/"
iso=$(ls "$work"/out-build/*.iso 2>/dev/null | head -n1)
[ -f "$iso" ] || { log "no ISO in $work/out-build"; ls -la "$work/out-build" >&2; exit 1; }
log "ISO $iso after ${elapsed}s"
echo "elapsed=$elapsed" >>"$work/build-vars.env"
else
	[ -f "$work/build-vars.env" ] || { log "no finished run $post_only"; exit 1; }
	# shellcheck disable=SC1091
	. "$work/build-vars.env"
	iso=$(ls "$work"/out-build/*.iso | head -n1)
fi
cd "$work"

# ---- 6b. FAT32 ESP (decision D17). kiwi 11.1.1 makes the embedded ESP with `mkdosfs -n BOOT FILE`
# (bootloader/config/grub2.py, _create_embedded_fat_efi_image): no -F, so mkfs.fat picks FAT16 for
# 30 MiB (15321 clusters), and the only knob, efifatimagesize, sets the size, not the FAT type
# (a size that gives >= 65525 clusters would need cluster size 512 B, which mkdosfs does not choose
# either). The Surface UEFI boots only from a FAT32 USB ESP. So the finished ISO is replayed with a
# 64 MiB FAT32 ESP made with the documented flags and the same EFI/BOOT files:
#   xorriso -boot_image any replay -append_partition 2 0xef ESP   (El Torito entry follows partition 2)
log "replacing the FAT16 ESP by a 64 MiB FAT32 ESP (D17)"
esp=$work/esp; rm -rf "$esp"; mkdir -p "$esp/files"
xorriso -osirrox on -indev "$iso" -extract_boot_images "$esp/old/" >/dev/null 2>&1
mcopy -n -s -i "$esp/old/eltorito_img1_uefi.img" ::EFI "$esp/files/"
# ---- D18: the stick boots Fedora's GRUB directly. On the Surface the firmware returned to its boot
# menu before GRUB with shim 16.1-7 as BOOTAA64.EFI (Secure Boot off; reason unknown, Hypothesis), and
# reached the Linux console with GRUB there (previous project, 2026-10-18). Secure Boot is off anyway
# (D9), so shim does nothing for us. EFI/BOOT after this step:
#   BOOTAA64.EFI = grubaa64.efi (byte-identical), shimaa64.efi = kiwi's shim (kept, unused),
#   mmaa64.efi (shim's MokManager, unused, kept), grubaa64.efi, grub.cfg (marker line first).
# bootx64.efi is removed: kiwi writes the aa64 shim under an x86 name (same size and content as
# bootaa64.efi, from its x86 fallback-name list); no arm64 firmware looks for it, and it would be a
# shim at a fallback path.
efib=$esp/files/EFI/BOOT
fnd() { find "$efib" -maxdepth 1 -iname "$1" | head -n1; }
if [ -z "$(fnd shimaa64.efi)" ]; then mv "$(fnd bootaa64.efi)" "$efib/shimaa64.efi"; fi   # re-runs: already renamed
rm -f "$(fnd bootx64.efi)"
rm -f "$(fnd bootaa64.efi)"
[ -n "$(fnd grubaa64.efi)" ] || { log "no grubaa64.efi in the ESP"; exit 1; }
cp "$(fnd grubaa64.efi)" "$efib/BOOTAA64.EFI"
marker='echo "SP11: GRUB started (direct EFI boot, no shim)"'
cfg=$(fnd grub.cfg)
grep -qxF "$marker" "$cfg" || { { echo "$marker"; cat "$cfg"; } >"$cfg.new" && mv "$cfg.new" "$cfg"; }
mkfs.fat -C -F 32 -s 1 -S 512 -n BOOT "$esp/esp32.img" 65536 >/dev/null
mcopy -s -i "$esp/esp32.img" "$esp/files/EFI" ::
xorriso -indev "$iso" -outdev "$iso.fat32" -boot_image any replay -append_partition 2 0xef "$esp/esp32.img" -commit >"$esp/xorriso.txt" 2>&1 \
	|| { tail -n 5 "$esp/xorriso.txt" >&2; log "xorriso replay failed"; exit 1; }
mv -f "$iso.fat32" "$iso"
# the replay changed the bytes the media tag of kiwi (implantisomd5) covers: tag again, or checkisomd5 fails
implantisomd5 --force --supported-iso "$iso" >"$esp/implant.txt" 2>&1 || { cat "$esp/implant.txt" >&2; log "implantisomd5 failed"; exit 1; }
rm -rf "$esp/old"

# ---- 7. the checks of the task: no quiet/rhgb/splash in any grub.cfg of the ISO and its ESP
log "grep check: quiet/rhgb/splash in every grub.cfg"
chk=$work/grubcheck
rm -rf "$chk"; mkdir -p "$chk"
for f in /boot/grub2/grub.cfg /boot/grub2/loopback.cfg /EFI/BOOT/grub.cfg /EFI/fedora/grub.cfg; do
	xorriso -osirrox on -indev "$iso" -extract "$f" "$chk/$(echo "$f" | tr / _)" >/dev/null 2>&1 || { log "FAIL: $f not in the ISO"; exit 1; }
done
xorriso -osirrox on -indev "$iso" -extract_boot_images "$chk/bi/" >/dev/null 2>&1
mcopy -i "$chk/bi/eltorito_img1_uefi.img" ::EFI/BOOT/grub.cfg "$chk/esp-grub.cfg"
for f in "$chk"/_* "$chk/esp-grub.cfg"; do
	if grep -v '^[[:space:]]*#' "$f" | grep -w -E 'quiet|rhgb|splash' >/dev/null; then log "FAIL: quiet/rhgb/splash in $f"; exit 1; fi
done
n=$(grep -c "^menuentry '" "$chk/_boot_grub2_grub.cfg"); [ "$n" = 8 ] || { log "FAIL: $n menu entries, expected 8 (M10)"; exit 1; }
for e in debug usbdbg nodsp wifi-unblock nomodeset initramfs notouch vmtest; do grep -q "sp11.entry=$e\$" "$chk/_boot_grub2_grub.cfg" || { log "FAIL: no entry with sp11.entry=$e"; exit 1; }; done
for f in x1p64100-microsoft-denali-m10 x1p64100-microsoft-denali-m10-notouch; do
	xorriso -indev "$iso" -find "/boot/dtb/qcom/$f.dtb" -type f 2>/dev/null | grep -q . || { log "FAIL: /boot/dtb/qcom/$f.dtb not on the ISO"; exit 1; }
done

# ---- 8. publish
mv -f "$iso" "$isodir/$name.iso"
( cd "$isodir" && sha256sum "$name.iso" >"$name.iso.sha256" )
sha=$(cut -d' ' -f1 "$isodir/$name.iso.sha256")

# ---- 9. build record
python3 - "$isodir/$name.json" "$name" "$sha" "$id" "$elapsed" "$work" "$REPO" "$OUT" "$pin" "$head" "${variants_smoke_copy:-0}" "$kind" "$private" <<'PYEOF'
import hashlib, json, os, re, subprocess, sys
rec, name, sha, bid, elapsed, work, repo, out, pin, head, variants_smoke_copy, kind, private = sys.argv[1:14]

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

pk = []
for l in read(f"{work}/out-build/Fedora.aarch64-44.packages").splitlines():
    f = l.split('|')
    if len(f) >= 5:
        pk.append(f"{f[0]}-{0 if f[1] == '(none)' else f[1]}:{f[2]}-{f[3]}.{f[4]}")
pk.sort()
fw = [l.split() for l in read(f"{out}/image-work/firmware-installed.sha256").splitlines() if l]
cfg = read(f"{work}/grubcheck/_boot_grub2_grub.cfg")
entries = []
for m in re.finditer(r"menuentry '([^']*)'.*?\{(.*?)\n\}", cfg, re.S):
    lin = re.search(r"^\s*linux \S+ (.*)$", m.group(2), re.M)
    entries.append({"title": m.group(1), "linux_args": lin.group(1).strip() if lin else None,
                    "devicetree": bool(re.search(r"^\s*devicetree ", m.group(2), re.M))})
series = f"{repo}/kernel/series"
manifest = f"{repo}/firmware/manifest.toml"
kernel_record_path = f"{out}/rpms/{read(f'{out}/image-work/kernel-nevra.txt').strip().replace('kernel-core-', 'kernel-')}.json"
patches = sorted(os.listdir(f"{repo}/image/kiwi/patches"))
series_paths = [''.join(line.split('#', 1)[0].split()) for line in read(series).splitlines()]
patch_series = ''.join(f"{p} {sha256(f'{repo}/{p}')}\n" for p in series_paths if p)
record = {
    "name": name, "kind": kind, "builder": "kiwi", "smoke": kind == "kiwi-smoke", "build_id": bid,
    "iso_sha256": sha, "iso_size": os.path.getsize(f"{out}/iso/{name}.iso"),
    "build_seconds": int(elapsed),
    "kernel_nevra": read(f"{out}/image-work/kernel-nevra.txt").strip(),
    "kernel_series_sha256": sha256(series) if os.path.exists(series) else None,
    "kernel_patch_series_sha256": hashlib.sha256(patch_series.encode()).hexdigest(),
    "firmware_manifest_sha256": sha256(manifest) if os.path.exists(manifest) else None,
    "firmware_installed": [{"sha256": a, "path": b} for a, b in fw],
    "firmware_installed_listing_sha256": hashlib.sha256("\n".join(" ".join(x) for x in fw).encode()).hexdigest(),
    "dtb": "qcom/x1p64100-microsoft-denali.dtb",
    "dtb_files": {f: sha256(f"{work}/dtb/boot/dtb/qcom/{f}") for f in sorted(os.listdir(f"{work}/dtb/boot/dtb/qcom"))},
    "dtb_variants_smoke_copy": variants_smoke_copy == "1",
    "dtb_variants_source": "out/dtb-variants/<kernel version>/qcom/ (kernel worker)",
    "dtb_variant_records": {f: json.load(open(f"{work}/dtb-records/{f}")) for f in sorted(os.listdir(f"{work}/dtb-records"))} if os.path.isdir(f"{work}/dtb-records") else {},
    "kernel_cmdline_reasons": "image/README.md, GRUB 2 and the kernel command line",
    "grub_entries": entries,
    "milestone": "M10",
    "kernel_release_record_sha256": sha256(kernel_record_path),
    "kernel_touch_modules": json.load(open(kernel_record_path))["m10"]["touch_modules"],
    "module_policy": {"qcom_battmgr": "blacklist + install false + dracut omit_drivers (D23)",
                      "ucsi_glink": "retained early", "ath12k.debug_mask": "0x30; CONFIG_ATH12K_DEBUG=y; output checked by L0"},
    "diagnostic_args_reason": {"usbdbg": "USB-C test-plan C + DSP R-I2, combined to contain trace volume",
                               "notouch": "touch-pen section 8: touch child disabled; debug arguments",
                               "nodsp": "DSP R-I3: PAS deferred until switch-root",
                               "wifi-unblock": "Wi-Fi I2: opt-in transient rfkill/NM probe"},
    "collector_sources": {c: sha256(f"{repo}/hardware/{c}/collector/{c}.sh") for c in ("dsp-subsystems", "wifi")},
    "touch_collector_sha256": sha256(f"{repo}/hardware/touch-pen/collect-read-only.sh"),
    "touch_userspace_collector_sha256": sha256(f"{repo}/image/overlay/usr/libexec/sp11-touch-userspace-collect"),
    "iptsd": json.load(open(f"{out}/rpms/iptsd-3.1.0-1.fc44.aarch64.json")),
    "component_inputs": json.load(open(f"{repo}/image/component-inputs/sources.json")),
    "kiwi_description": {"url": "https://pagure.io/fedora-kiwi-descriptions.git", "branch": "f44", "pinned_commit": pin,
                         "branch_head_at_build": head, "profile": "Workstation-Live", "kiwi_file": "Fedora.kiwi",
                         "sp11_patches": patches},
    "repos": read(f"{work}/repos.txt").strip().splitlines(),
    "container_image": os.environ.get("SP11_IMAGE_ID", ""),
    "package_count": len(pk), "packages": pk,
    "tools": {t: subprocess.run(["rpm", "-q", t], capture_output=True, text=True).stdout.strip()
              for t in ("kiwi-cli", "dnf5", "grub2-efi-aa64", "shim-aa64", "dracut", "xorriso", "erofs-utils")},
}
if private == "1":
    # hash prefixes and the board hash only (image/tools/private-stage.py); never an address
    record["private"] = json.load(open(f"{work}/private-record.json"))
    record["distribution"] = "forbidden: contains device addresses and Windows-derived board data"
json.dump(record, open(rec, "w"), indent=1)
PYEOF
log "done: $isodir/$name.iso ($sha)"
log "record: $isodir/$name.json"
