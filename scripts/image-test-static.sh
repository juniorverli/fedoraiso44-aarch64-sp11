#!/usr/bin/env bash
# L0 static checks of an SP11 ISO (decision D10, image/README.md "L0 static checks").
#
#   scripts/image-test-static.sh [ISO | NAME]      default: newest out/iso/*.iso
#
# Runs in the container of scripts/image-container.sh (re-executes itself there). Reads the
# ISO and its build record out/iso/<name>.json; changes nothing but its work directory
# out/image-work/l0-<name>/. Exit status 0 only when every check passed; a check that
# cannot apply to a smoke build is reported as SKIP, never as PASS.
# Report: stdout and out/iso/<name>.l0.txt.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [ "${SP11_OUT:-}" = "" ] || [ ! -d /sp11 ]; then
	exec "$here/scripts/image-container.sh" run /sp11/scripts/image-test-static.sh "$@"
fi
OUT=$SP11_OUT
REPO=/sp11

arg=${1:-}
if [ -z "$arg" ]; then
	iso=$(ls -t "$OUT"/iso/*.iso 2>/dev/null | head -n1)
elif [ -f "$arg" ]; then
	iso=$arg
elif [ -f "$OUT/iso/$arg" ]; then
	iso=$OUT/iso/$arg
else
	iso=$OUT/iso/$arg.iso
fi
[ -f "$iso" ] || { echo "image-test-static: no ISO ($arg)" >&2; exit 2; }
iso=$(readlink -f "$iso")
name=$(basename "$iso" .iso)
rec=${iso%.iso}.json
[ -f "$rec" ] || { echo "image-test-static: build record $rec missing" >&2; exit 2; }
W=$OUT/image-work/l0-$name
report=${iso%.iso}.l0.txt
mkdir -p "$W"
: >"$report"

npass=0 nfail=0 nskip=0
say() { echo "$*" | tee -a "$report"; }
pass() { npass=$((npass + 1)); say "PASS $1: $2"; }
fail() { nfail=$((nfail + 1)); say "FAIL $1: $2"; }
skip() { nskip=$((nskip + 1)); say "SKIP $1: $2"; }
jq_() { jq -r "$1" "$rec"; }

smoke=$(jq_ '.smoke')
# D16: the record says which builder made the ISO. kiwi and livemedia-creator lay the media out
# differently; each difference below is marked "kiwi:" and listed in image/README.md ("L0 on kiwi").
builder=$(jq_ '.builder // "lmc"')
dtb=$(jq_ '.dtb')
want_nevra=$(jq_ '.kernel_nevra')
say "L0 static checks: $name (sha256 in record: $(jq_ '.iso_sha256' | cut -c1-16)..., smoke=$smoke)"
actual=$(sha256sum "$iso" | cut -d' ' -f1)
[ "$actual" = "$(jq_ '.iso_sha256')" ] && pass 0.1 "ISO SHA-256 equals the build record" || fail 0.1 "ISO SHA-256 differs from the build record"

ROOT=$W/root
cleanup() { for m in "$W/root2" "$W/root"; do findmnt -n "$m" >/dev/null 2>&1 && umount "$m" 2>/dev/null; done; return 0; }
trap cleanup EXIT

# --------------------------------------------------------------- extract ----
x() { xorriso -osirrox on -indev "$iso" -extract "$1" "$2" >/dev/null 2>&1; }
rm -rf "$W/iso-tree"
mkdir -p "$W/iso-tree"
x /EFI "$W/iso-tree/EFI"
if [ "$builder" = kiwi ]; then
	# kiwi: kernel, initrd, DTB and the real grub.cfg are under /boot; the embedded ESP is only
	# the GPT partition 2 / El Torito image (no /images/efiboot.img)
	x /boot "$W/iso-tree/boot"
	chmod -R u+rw "$W/iso-tree" 2>/dev/null
	kimg=$W/iso-tree/boot/aarch64/loader/linux
	initrd_img=$W/iso-tree/boot/aarch64/loader/initrd
	rm -rf "$W/boot-images"
	xorriso -osirrox on -indev "$iso" -extract_boot_images "$W/boot-images/" >/dev/null 2>&1
	esp_img=$W/boot-images/eltorito_img1_uefi.img
	dtb_iso_path=/boot/dtb/$dtb
else
	x /images "$W/iso-tree/images-small" # includes pxeboot and efiboot.img (squashfs is under /LiveOS)
	for f in .treeinfo .discinfo; do x "/$f" "$W/iso-tree/$f"; done
	chmod -R u+rw "$W/iso-tree" 2>/dev/null
	kimg=$W/iso-tree/images-small/pxeboot/vmlinuz
	initrd_img=$W/iso-tree/images-small/pxeboot/initrd.img
	esp_img=$W/iso-tree/images-small/efiboot.img
	dtb_iso_path=/images/pxeboot/dtb/$dtb
fi

# ---------------------------------------------------------------- check 1 ----
xorriso -indev "$iso" -report_el_torito plain >"$W/eltorito.txt" 2>&1
if grep -q -i -E 'efi|0xef' "$W/eltorito.txt"; then pass 1.1 "El Torito EFI boot image present"; else fail 1.1 "no El Torito EFI entry ($W/eltorito.txt)"; fi
sgdisk -p "$iso" >"$W/gpt.txt" 2>&1
if ! grep -q -i -E 'invalid|corrupt|not found' "$W/gpt.txt" && grep -E '^ +2 ' "$W/gpt.txt" | grep -q -E 'EF00'; then
	pass 1.2 "hybrid: valid GPT, partition 2 is the EFI system partition (EF00)"
else
	fail 1.2 "no GPT with an EFI partition 2 ($W/gpt.txt)"
fi
sgdisk -i 2 "$iso" >"$W/gpt2.txt" 2>&1
start=$(awk -F'[: ]+' '/First sector/{print $3}' "$W/gpt2.txt")
if [ -n "$start" ] && [ -f "$esp_img" ] && dd if="$iso" bs=512 skip="$start" count=$(($(stat -c %s "$esp_img") / 512)) status=none 2>/dev/null | cmp -s - "$esp_img"; then
	pass 1.3 "GPT partition 2 is identical to the El Torito/efiboot ESP image"
else
	fail 1.3 "GPT partition 2 differs from images/efiboot.img (start sector '${start:-?}')"
fi
# D17: the Surface UEFI boots only from a FAT32 USB ESP. Decided by the cluster count of the BPB
# (>= 65525 is FAT32 by definition) and by the size (>= 64 MiB), never by the label. The image that
# El Torito points to and GPT partition 2 must be the same FAT32 image.
python3 -I - "$esp_img" "$iso" "$(awk -F'[: ]+' '/First sector/{print $3}' "$W/gpt2.txt")" "$(awk -F'[: ]+' '/Partition size/{print $3}' "$W/gpt2.txt")" <<'PY' >"$W/esp-fat.txt"
import struct, sys
esp, iso, start, size = sys.argv[1], sys.argv[2], int(sys.argv[3] or 0), int(sys.argv[4] or 0)
def bpb(b):
    bps = struct.unpack_from('<H', b, 11)[0]; spc = b[13]; rsv = struct.unpack_from('<H', b, 14)[0]; nfat = b[16]
    rootent = struct.unpack_from('<H', b, 17)[0]; tot16 = struct.unpack_from('<H', b, 19)[0]
    fat16 = struct.unpack_from('<H', b, 22)[0]; tot32 = struct.unpack_from('<I', b, 32)[0]; fat32 = struct.unpack_from('<I', b, 36)[0]
    tot = tot16 or tot32; fsz = fat16 or fat32
    rootsec = (rootent * 32 + bps - 1) // bps
    return (tot - rsv - nfat * fsz - rootsec) // spc, tot * bps, bps, spc
a = open(esp, 'rb').read(4096)
n_el, size_el, bps, spc = bpb(a)
f = open(iso, 'rb'); f.seek(start * 512); g = f.read(4096)
n_gpt, size_gpt, _, _ = bpb(g)
import os
same = False
if start:
    import hashlib
    h1 = hashlib.sha256(); h2 = hashlib.sha256(); L = os.path.getsize(esp)
    with open(esp, 'rb') as x: 
        for c in iter(lambda: x.read(1 << 20), b''): h1.update(c)
    f.seek(start * 512); left = L
    while left:
        c = f.read(min(1 << 20, left)); h2.update(c); left -= len(c)
    same = h1.hexdigest() == h2.hexdigest()
print(f"{n_el} {size_el} {n_gpt} {size_gpt} {int(same)} {bps} {spc}")
PY
read -r n_el size_el n_gpt size_gpt same_img bps spc <"$W/esp-fat.txt"
if [ -n "${n_el:-}" ] && [ "$n_el" -ge 65525 ] && [ "$n_gpt" -ge 65525 ]; then pass 1.5 "ESP is FAT32 by cluster count: El Torito image $n_el clusters, GPT partition 2 $n_gpt clusters (>= 65525)"; else fail 1.5 "ESP is not FAT32 by cluster count (El Torito ${n_el:-?}, GPT ${n_gpt:-?}; FAT16 has < 65525)"; fi
if [ -n "${size_el:-}" ] && [ "$size_el" -ge 67108864 ] && [ "$size_gpt" -ge 67108864 ]; then pass 1.6 "ESP size $((size_el / 1048576)) MiB >= 64 MiB"; else fail 1.6 "ESP smaller than 64 MiB (El Torito ${size_el:-?} B, GPT ${size_gpt:-?} B)"; fi
[ "${same_img:-0}" = 1 ] && pass 1.7 "El Torito UEFI image and GPT partition 2 are the same bytes" || fail 1.7 "El Torito UEFI image and GPT partition 2 differ"
if checkisomd5 "$iso" >"$W/checkisomd5.txt" 2>&1; then pass 1.4 "checkisomd5 passes"; else fail 1.4 "checkisomd5 failed ($(tail -n1 "$W/checkisomd5.txt"))"; fi

# ---------------------------------------------------------------- check 2 ----
cfg_iso=$W/iso-tree/EFI/BOOT/grub.cfg
cfg_esp=$W/esp-grub.cfg
mcopy -n -i "$esp_img" ::EFI/BOOT/grub.cfg "$cfg_esp" 2>/dev/null
if [ "$builder" = kiwi ]; then
	# kiwi: the menu lives in /boot/grub2/grub.cfg on the ISO file system. The ISO's EFI/BOOT and
	# EFI/fedora grub.cfg and the one in the embedded ESP are stubs: `search` + `configfile` to it.
	cfg_main=$W/iso-tree/boot/grub2/grub.cfg
	x /EFI/fedora/grub.cfg "$W/iso-tree/EFI/fedora-grub.cfg"
	for pair in "iso-EFI/BOOT:$cfg_iso" "iso-EFI/fedora:$W/iso-tree/EFI/fedora-grub.cfg" "esp:$cfg_esp" "main:$cfg_main"; do
		tag=${pair%%:*} cfg=${pair#*:}
		[ -s "$cfg" ] || { fail 2.1 "$tag grub.cfg missing"; continue; }
		if grep -v '^[[:space:]]*#' "$cfg" | grep -w -E 'quiet|rhgb|splash' >/dev/null; then fail 2.1 "$tag grub.cfg has quiet/rhgb/splash"; else pass 2.1 "$tag grub.cfg has no quiet/rhgb/splash"; fi
	done
	grep -q '^set timeout_style=menu' "$cfg_main" && grep -E '^set timeout=[1-9]' "$cfg_main" >/dev/null && pass 2.2 "main grub.cfg shows the menu (timeout_style=menu, timeout>0)" || fail 2.2 "main grub.cfg may hide the menu"
	stub_ok=1
	for c in "$cfg_iso" "$W/iso-tree/EFI/fedora-grub.cfg" "$cfg_esp"; do
		grep -v '^[[:space:]]*$' "$c" | grep -q -v -E '^(echo \"SP11: GRUB started \(direct EFI boot, no shim\)\"$|search --file --set=root /boot/|set prefix=\(\$root\)/boot/grub2$|configfile \(\$root\)/boot/grub2/grub.cfg$)' && stub_ok=0
	done
	[ "$stub_ok" = 1 ] && pass 2.3 "the three EFI grub.cfg are stubs that chain to /boot/grub2/grub.cfg" || fail 2.3 "an EFI grub.cfg is more than a chain stub"
	other=$(xorriso -indev "$iso" -find / -name '*.cfg' 2>/dev/null | grep -i grub | grep -v -E "^'/(EFI/BOOT/grub.cfg|EFI/fedora/grub.cfg|boot/grub2/grub.cfg|boot/grub2/loopback.cfg)'$" || true)
	[ -z "$other" ] && pass 2.4 "no other grub config in the ISO (loopback.cfg only sources the main one)" || fail 2.4 "other grub config: $other"
	[ "$(grep -c . "$W/iso-tree/boot/grub2/loopback.cfg")" = 1 ] && grep -q '^source /boot/grub2/grub.cfg$' "$W/iso-tree/boot/grub2/loopback.cfg" || fail 2.4 "loopback.cfg is not a plain source line"
	cfg_esp=$cfg_main   # the entry checks below read the main config
else
	for pair in "iso:$cfg_iso" "esp:$cfg_esp"; do
		tag=${pair%%:*} cfg=${pair#*:}
		[ -s "$cfg" ] || { fail 2.1 "$tag grub.cfg missing"; continue; }
		if grep -v '^[[:space:]]*#' "$cfg" | grep -w -E 'quiet|rhgb|splash' >/dev/null; then fail 2.1 "$tag grub.cfg has quiet/rhgb/splash"; else pass 2.1 "$tag grub.cfg has no quiet/rhgb/splash"; fi
		if grep -q '^set timeout_style=menu' "$cfg" && grep -E '^set timeout=[1-9]' "$cfg" >/dev/null; then pass 2.2 "$tag grub.cfg shows the menu (timeout_style=menu, timeout>0)"; else fail 2.2 "$tag grub.cfg may hide the menu"; fi
	done
	cmp -s "$cfg_iso" "$cfg_esp" && pass 2.3 "ISO and ESP grub.cfg are identical" || fail 2.3 "ISO and ESP grub.cfg differ"
	# any other grub.cfg anywhere in the ISO
	other=$(xorriso -indev "$iso" -find / -name 'grub*.cfg' 2>/dev/null | grep -v -E "^'/EFI/BOOT/grub.cfg'$" || true)
	[ -z "$other" ] && pass 2.4 "no other grub.cfg in the ISO" || fail 2.4 "other grub config: $other"
fi
titles=$(grep -o "^menuentry '[^']*'" "$cfg_esp" | sed "s/menuentry '//;s/'\$//")
if [ "$builder" = kiwi ]; then
	# M5 (D21): the six entries of the menu, in this order
	expect=$'SP11 debug\nSP11 debug, GPU on\nSP11 debug, GPU on + DRM trace\nSP11 debug nomodeset\nSP11 debug, stop in initramfs\nVM test (no devicetree)'
	nentries=6
else
	expect=$'SP11 debug\nSP11 debug + DRM trace\nSP11 debug nomodeset\nSP11 debug, stop in initramfs\nVM test (no devicetree)'
	nentries=5
fi
[ "$titles" = "$expect" ] && pass 2.5 "exactly the $nentries entries, in order" || fail 2.5 "entries differ: $(echo "$titles" | tr '\n' '|')"
[ "$(grep -c '^set default=0' "$cfg_esp")" = 1 ] && pass 2.6 "default entry is the first (SP11 debug)" || fail 2.6 "default is not entry 0"
bad=0
awk '/^menuentry /{t=$0} /^\tdevicetree /{print $2 "\t" t}' "$cfg_esp" >"$W/dt-lines.txt"
while IFS=$'\t' read -r path entry; do
	path=${path#'($root)'}   # kiwi writes devicetree ($root)/boot/dtb/...
	p=${path#/}
	if xorriso -indev "$iso" -find "/$p" -type f 2>/dev/null | grep -q .; then :; else bad=1; fail 2.7 "devicetree target /$p missing ($entry)"; fi
done <"$W/dt-lines.txt"
sp11_entries=$(grep -c "^menuentry 'SP11" "$cfg_esp")
[ "$(wc -l <"$W/dt-lines.txt")" -eq "$sp11_entries" ] && [ "$sp11_entries" -gt 0 ] || { bad=1; fail 2.7 "not every SP11 entry has a devicetree line"; }
[ "$bad" = 0 ] && pass 2.7 "every SP11 entry has a devicetree line to a file that exists"
# D15 / D9: every entry names itself on the command line; only the VM entry has the serial console
ids_ok=1
awk '/^menuentry /{t=$0} /^[[:space:]]+linux /{print t "\t" $0}' "$cfg_esp" >"$W/linux-lines.txt"
while IFS=$'\t' read -r t l; do
	id=$(echo "$t" | sed -n "s/.*--id sp11-\([a-z0-9-]*\).*/\1/p")
	case $id in debug | gpu | gpu-drm-trace | nomodeset | initramfs | vmtest) ;; *) ids_ok=0; fail 2.12 "unknown entry id '$id' ($t)" ;; esac
	want=$id
	case $l in *" sp11.entry=$want"*) ;; *) ids_ok=0; fail 2.12 "entry '$t' lacks sp11.entry=$want" ;; esac
	case $l in *console=ttyAMA0*) [ "$id" = vmtest ] || { ids_ok=0; fail 2.12 "serial console on a device entry: $t"; } ;; *) [ "$id" != vmtest ] || { ids_ok=0; fail 2.12 "VM entry lacks the serial console"; } ;; esac
	case $l in *" debug "*loglevel=8*ignore_loglevel*) ;; *) ids_ok=0; fail 2.12 "entry '$t' is not verbose (debug loglevel=8 ignore_loglevel)" ;; esac
done <"$W/linux-lines.txt"
[ "$ids_ok" = 1 ] && [ "$(wc -l <"$W/linux-lines.txt")" = "$nentries" ] && pass 2.12 "every entry has sp11.entry=<id> and is verbose; serial console only on the VM entry"
vm=$(awk '/^menuentry .VM test/{f=1} f&&/^[[:space:]]+devicetree /{print "x"}' "$cfg_esp")
[ -z "$vm" ] && pass 2.8 "VM test entry has no devicetree" || fail 2.8 "VM test entry has a devicetree line"
[ "$(grep -c "^menuentry '" "$cfg_esp")" = "$nentries" ] && [ "$(grep '^set default' "$cfg_esp")" = "set default=0" ] && pass 2.9 "VM test entry is not the default"
if [ "$builder" = kiwi ]; then
	# D21: every device entry has clk_ignore_unused pd_ignore_unused rootdelay=10; the DTB is m5 (GPU off) except on the two
	# GPU entries (m5gpu); each adds at most one argument; nothing else (no blacklist, no earlier DTB).
	d19=1
	while IFS=$'\t' read -r t l; do
		id=$(echo "$t" | sed -n "s/.*--id sp11-\([a-z0-9-]*\).*/\1/p")
		case $id in
		vmtest) base=0; extra=; want= ;;
		gpu) base=1; extra=; want=x1p64100-microsoft-denali-m5gpu.dtb ;;
		gpu-drm-trace) base=1; extra=drm.debug=0x1ff; want=x1p64100-microsoft-denali-m5gpu.dtb ;;
		nomodeset) base=1; extra=nomodeset; want=x1p64100-microsoft-denali-m5.dtb ;;
		initramfs) base=1; extra=rd.break=pre-mount; want=x1p64100-microsoft-denali-m5.dtb ;;
		*) base=1; extra=; want=x1p64100-microsoft-denali-m5.dtb ;;
		esac
		case $l in *" clk_ignore_unused pd_ignore_unused rootdelay=10"*) have=1 ;; *) have=0 ;; esac
		[ "$base" = "$have" ] || { d19=0; fail 2.17 "entry $id: clk_ignore_unused pd_ignore_unused rootdelay=10 expected=$base found=$have"; }
		for x in rd.driver.blacklist=qcom_q6v5_pas drm.debug=0x1ff nomodeset rd.break=pre-mount; do
			case $l in *" $x "*) [ "$x" = "$extra" ] || { d19=0; fail 2.17 "entry $id carries $x"; } ;; *) [ "$x" != "$extra" ] || { d19=0; fail 2.17 "entry $id lacks $x"; } ;; esac
		done
		if [ -n "$want" ]; then
			got=$(awk -v t="$t" '$0==t{f=1;next} /^menuentry /{f=0} f&&/^\tdevicetree /{print $2}' "$cfg_esp")
			[ "$got" = "(\$root)/boot/dtb/qcom/$want" ] || { d19=0; fail 2.17 "entry $id loads '$got', expected qcom/$want"; }
		fi
	done <"$W/linux-lines.txt"
	[ "$d19" = 1 ] && pass 2.17 "M5 menu: every device entry has clk_ignore_unused pd_ignore_unused rootdelay=10, the m5 DTB (m5gpu on the two GPU entries) and at most its one extra argument"
fi
if [ "$builder" = kiwi ]; then
	# S1 (D21): no device entry may load a DTB that enables the sound card or the WSA8845 speaker amplifiers. Every DTB a
	# devicetree line of a device entry points to is decompiled with dtc and judged by the kernel worker's script.
	s1ok=1
	for dp in $(awk '/^\tdevicetree /{print $2}' "$cfg_esp" | sort -u); do
		dp=${dp#'($root)'}
		df=$W/s1-$(basename "$dp"); x "$dp" "$df"
		if [ ! -s "$df" ] || ! dtc -I dtb -O dts -o "$df.dts" "$df" 2>/dev/null; then s1ok=0; fail 2.18 "cannot decompile $dp for the sound check"; continue; fi
		# the kernel worker's scripts/kernel-dtb-safety.py: effective status (a node is enabled only if every ancestor is),
		# watching the WSA8845 SoundWire ID, wsa884* and the x1e80100 sound card; it also needs the nodes to be present
		python3 -I "$REPO/scripts/kernel-dtb-safety.py" "$df.dts" >"$df.s1.json" 2>&1 && res=OK || res="effectively enabled or no watched node: $(tr -d '\n ' <"$df.s1.json" | cut -c1-300)"
		[ "$res" = OK ] || { s1ok=0; fail 2.18 "S1: $dp: $res"; }
	done
	[ "$s1ok" = 1 ] && pass 2.18 "S1: no DTB of any device entry enables /sound, &swr0 (soundwire@6b10000) or a WSA884x speaker node"
fi
free=$(mdir -i "$esp_img" ::/ 2>/dev/null | awk '/bytes free/{gsub(/[^0-9]/,""); print}')
if [ -n "${free:-}" ] && [ "$free" -ge 8388608 ]; then pass 2.10 "embedded ESP has $((free / 1048576)) MiB free for /EFI/sp11-logs"; else fail 2.10 "embedded ESP free space too small (${free:-?} bytes)"; fi
for f in BOOTAA64.EFI grubaa64.efi mmaa64.efi grub.cfg; do
	mdir -i "$esp_img" "::EFI/BOOT/$f" >/dev/null 2>&1 || fail 2.11 "ESP lacks EFI/BOOT/$f"
done
if [ "$builder" = kiwi ]; then
	# D18: the stick boots GRUB directly; the Surface firmware returned to its menu with shim as BOOTAA64.EFI
	d=$W/esp-d18; rm -rf "$d"; mkdir -p "$d"
	for f in BOOTAA64.EFI grubaa64.efi shimaa64.efi grub.cfg; do mcopy -n -i "$esp_img" "::EFI/BOOT/$f" "$d/$f" 2>/dev/null; done
	if [ -s "$d/BOOTAA64.EFI" ] && cmp -s "$d/BOOTAA64.EFI" "$d/grubaa64.efi"; then pass 2.13 "EFI/BOOT/BOOTAA64.EFI is byte-identical to grubaa64.efi"; else fail 2.13 "BOOTAA64.EFI is not byte-identical to grubaa64.efi"; fi
	[ -s "$d/shimaa64.efi" ] && ! cmp -s "$d/BOOTAA64.EFI" "$d/shimaa64.efi" && pass 2.14 "shim is kept as shimaa64.efi and is not the fallback loader" || fail 2.14 "shimaa64.efi missing or equal to BOOTAA64.EFI"
	[ "$(head -n1 "$d/grub.cfg")" = 'echo "SP11: GRUB started (direct EFI boot, no shim)"' ] && pass 2.15 "ESP grub.cfg starts with the SP11 marker line" || fail 2.15 "ESP grub.cfg lacks the marker line as first line"
	other=$(mdir -b -i "$esp_img" ::EFI/BOOT 2>/dev/null | tr 'A-Z' 'a-z' | sort | tr '\n' ' ')
	case "$other" in *bootx64.efi*) fail 2.16 "bootx64.efi (an aa64 shim under an x86 name) is on the ESP" ;; *) pass 2.16 "no bootx64.efi on the ESP (files: $other)" ;; esac
fi

# --------------------------------------------------- squashfs and rootfs ----
# livemedia-creator --no-virt puts the root tree directly into LiveOS/squashfs.img (no inner
# rootfs.img); dracut's dmsquash-live accepts both. Mount the squashfs; fall back to rootfs.img.
if [ ! -f "$W/squashfs.img" ]; then
	say "...extracting LiveOS/squashfs.img (a few minutes)"
	x /LiveOS/squashfs.img "$W/squashfs.img"
fi
mkdir -p "$ROOT"
cleanup
layout=squashfs
if [ "$builder" = kiwi ]; then
	# kiwi: Fedora's description makes the live root an erofs image (lzma). The WSL2 kernel mounts
	# erofs only without lzma ("Failed to mount erofs: Operation not supported"), so L0 unpacks it
	# in user space with fsck.erofs --extract into the work directory (a few minutes, ~7 GiB).
	layout=erofs
	if [ ! -f "$W/.erofs-extracted" ]; then
		say "...unpacking the erofs root with fsck.erofs (several minutes)"
		rm -rf "$ROOT"; mkdir -p "$ROOT"
		if ! fsck.erofs --extract="$ROOT" --overwrite "$W/squashfs.img" >"$W/erofs-extract.txt" 2>&1; then
			fail 0.2 "cannot unpack LiveOS/squashfs.img: $(tail -n2 "$W/erofs-extract.txt")"
			say "SUMMARY: $npass passed, $nfail failed, $nskip skipped"
			exit 1
		fi
		touch "$W/.erofs-extracted"
	fi
elif ! mount -t squashfs -o loop,ro "$W/squashfs.img" "$ROOT" 2>"$W/mount.txt"; then
	fail 0.2 "cannot mount LiveOS/squashfs.img: $(cat "$W/mount.txt")"
	say "SUMMARY: $npass passed, $nfail failed, $nskip skipped"
	exit 1
fi
if [ -f "$ROOT/LiveOS/rootfs.img" ]; then
	layout=rootfs.img
	mkdir -p "$W/root2"
	mount -o loop,ro "$ROOT/LiveOS/rootfs.img" "$W/root2" && ROOT=$W/root2
fi
pass 0.2 "LiveOS/squashfs.img readable (layout: $layout)"
kver=$(ls "$ROOT/lib/modules" 2>/dev/null | head -n1)
[ -n "$kver" ] && [ "$(ls "$ROOT/lib/modules" | wc -l)" = 1 ] && pass 0.3 "exactly one kernel in the image: $kver" || fail 0.3 "kernel directories: $(ls "$ROOT/lib/modules" 2>/dev/null | tr '\n' ' ')"
rpm --root "$ROOT" -qla 2>/dev/null | sort >"$W/rpm-files.txt"

# ---------------------------------------------------------------- check 3 ----
dtbf=$W/denali.dtb
x "$dtb_iso_path" "$dtbf"
if [ -s "$dtbf" ]; then
	pass 3.1 "DTB $dtb present on the ISO"
	if dtc -I dtb -O dts -o "$W/denali.dts" "$dtbf" 2>"$W/dtc.txt"; then pass 3.2 "DTB decompiles with dtc"; else fail 3.2 "dtc failed: $(head -n3 "$W/dtc.txt")"; fi
	rootcompat=$(fdtget "$dtbf" / compatible 2>/dev/null)
	if [ "$smoke" = true ]; then
		skip 3.3 "smoke build with $dtb: Denali root compatible and node list not applicable (root: $rootcompat)"
	else
		case " $rootcompat " in *" microsoft,denali-lcd "*) pass 3.3 "root compatible has microsoft,denali-lcd ($rootcompat)" ;; *) fail 3.3 "root compatible is '$rootcompat'" ;; esac
		miss=0
		norm() { tr -s ' \t\n' ' ' | sed 's/ $//'; }
		dts_norm=$(norm <"$W/denali.dts")
		while IFS= read -r line; do
			case $line in '' | '#'*) continue ;; esac
			l=$(echo "$line" | norm)
			case "$dts_norm" in *"$l"*) ;; *) miss=1; fail 3.4 "DTB lacks: $line" ;; esac
		done <"$REPO/image/expected-dtb.txt"
		[ "$miss" = 0 ] && pass 3.4 "every line of image/expected-dtb.txt is in the DTB"
	fi
	cmp -s "$dtbf" "$ROOT/lib/modules/$kver/dtb/$dtb" && pass 3.5 "ISO DTB equals the kernel package DTB" || fail 3.5 "ISO DTB differs from lib/modules/$kver/dtb/$dtb"
else
	fail 3.1 "DTB $dtb_iso_path missing"
fi

if [ "$builder" = kiwi ]; then
	# D19: DTB variants next to the packaged one. Same SoC and board (root compatible), different from the
	# packaged DTB, hashes as in the build record and as in out/dtb-variants (the kernel worker's output).
	for v in m5 m5gpu parity edponly nobl; do
		vf=x1p64100-microsoft-denali-$v.dtb
		vd=$W/$vf
		x "/boot/dtb/qcom/$vf" "$vd"
		if [ ! -s "$vd" ]; then
			if [ "$v" = m5 ] || [ "$v" = m5gpu ]; then fail 3.6 "variant DTB /boot/dtb/qcom/$vf missing on the ISO"; else skip 3.6 "variant $v is not on the ISO (unreferenced in M5, optional)"; fi
			continue
		fi
		dtc -I dtb -O dts -o "$vd.dts" "$vd" 2>"$vd.err" && pass 3.6 "variant $v decompiles with dtc" || fail 3.6 "variant $v: dtc failed: $(head -n2 "$vd.err")"
		rc=$(fdtget "$vd" / compatible 2>/dev/null)
		case " $rc " in *" microsoft,denali-lcd "*) pass 3.7 "variant $v root compatible has microsoft,denali-lcd" ;; *) fail 3.7 "variant $v root compatible is '$rc'" ;; esac
		vsha=$(sha256sum "$vd" | cut -d' ' -f1)
		if [ "$(jq_ ".dtb_variants_smoke_copy // false")" = true ]; then
			skip 3.8 "smoke build: variant $v is a copy of the packaged DTB, not a real variant"
		else
			cmp -s "$vd" "$dtbf" && fail 3.8 "variant $v is identical to the packaged DTB" || pass 3.8 "variant $v differs from the packaged DTB"
		fi
		[ "$vsha" = "$(jq_ ".dtb_files[\"$vf\"] // empty")" ] && pass 3.9 "variant $v SHA-256 equals the build record" || fail 3.9 "variant $v SHA-256 $vsha differs from the build record ($(jq_ ".dtb_files[\"$vf\"] // \"none\""))"
		rsha=$(jq_ ".dtb_variant_records[\"$vf.json\"].sha256 // empty")
		if [ -n "$rsha" ]; then [ "$vsha" = "$rsha" ] && pass 3.11 "variant $v SHA-256 equals the kernel worker's JSON record" || fail 3.11 "variant $v SHA-256 differs from the kernel worker's JSON record ($rsha)"; else skip 3.11 "no JSON record of the kernel worker for variant $v in the build record"; fi
		src=$(ls "$OUT"/dtb-variants/"$kver"/qcom/$vf 2>/dev/null | head -n1)
		if [ -n "$src" ]; then cmp -s "$src" "$vd" && pass 3.10 "variant $v equals out/dtb-variants/$kver/qcom/$vf" || fail 3.10 "variant $v differs from $src"; else skip 3.10 "no out/dtb-variants/$kver/qcom/$vf to compare with"; fi
	done
fi

# ---------------------------------------------------------------- check 4 ----
got_nevra=$(rpm --root "$ROOT" -q kernel-core --qf '%{name}-%{version}-%{release}.%{arch}' 2>/dev/null)
[ -n "$want_nevra" ] && [ "$got_nevra" = "$want_nevra" ] && pass 4.1 "kernel-core in the image is $got_nevra = build record" || fail 4.1 "kernel-core '$got_nevra' != record '$want_nevra'"
if [ "$smoke" = false ]; then
	ls "$OUT"/rpms/kernel-core-*.rpm >/dev/null 2>&1 && { rpm -qp --qf '%{name}-%{version}-%{release}.%{arch}\n' "$OUT"/rpms/kernel-core-*.rpm | grep -qx "$got_nevra" && pass 4.2 "kernel-core is the RPM of out/rpms" || fail 4.2 "kernel-core is not in out/rpms"; }
fi
cmp -s "$kimg" "$ROOT/lib/modules/$kver/vmlinuz" && pass 4.3 "ISO kernel image equals lib/modules/$kver/vmlinuz" || fail 4.3 "ISO kernel image differs from the package"
kimg_ver=$(python3 -I - "$kimg" <<'PY'
import gzip, lzma, re, struct, sys
d = open(sys.argv[1], 'rb').read()
if d[4:8] == b'zimg':                       # EFI zboot: payload offset/size at 8/12, type at 24
    off, size = struct.unpack_from('<II', d, 8)
    typ = d[24:32].split(b'\0')[0]
    p = d[off:off + size]
    try:
        if typ == b'gzip':
            d = gzip.decompress(p)
        elif typ == b'xz':
            d = lzma.decompress(p)
        elif typ == b'zstd':
            import subprocess
            d = subprocess.run(['zstd', '-dc'], input=p, capture_output=True).stdout
    except Exception:
        pass
m = re.search(rb'Linux version (\S+)', d)
print(m.group(1).decode() if m else '')
PY
)
if [ "$kimg_ver" = "$kver" ]; then pass 4.4 "kernel image says 'Linux version $kimg_ver'"; elif [ -z "$kimg_ver" ]; then skip 4.4 "version string not found in the kernel image"; else fail 4.4 "kernel image says '$kimg_ver', package says $kver"; fi
cfgk=$ROOT/lib/modules/$kver/config
[ -f "$cfgk" ] || cfgk=$(ls "$ROOT"/boot/config-* 2>/dev/null | head -n1)
if [ -f "$cfgk" ]; then
	for s in CONFIG_DEBUG_INFO_BTF CONFIG_DEBUG_INFO_BTF_MODULES; do grep -qx "$s=y" "$cfgk" && pass 4.5 "$s=y" || fail 4.5 "$s is not y"; done
	grep -qx 'CONFIG_SQUASHFS_ZSTD=y' "$cfgk" && pass 4.6 "CONFIG_SQUASHFS_ZSTD=y (the image uses zstd squashfs)" || fail 4.6 "CONFIG_SQUASHFS_ZSTD not y but the squashfs is zstd"
	if [ "$smoke" = false ]; then
		bad=0
		while IFS= read -r l; do
			case $l in '' | '#'*) continue ;; esac
			sym=${l%%=*}
			if ! grep -qx -- "$l" "$cfgk"; then bad=1; fail 4.7 "shipped config lacks '$l' (has: $(grep -E "^(# )?$sym[= ]" "$cfgk" | head -n1))"; fi
		done <"$REPO/kernel/config/sp11.config"
		[ "$bad" = 0 ] && pass 4.7 "every symbol of kernel/config/sp11.config has its value in the shipped config"
	else
		skip 4.7 "smoke build: Fedora kernel, kernel/config/sp11.config not applicable"
	fi
else
	fail 4.5 "no kernel config in the image"
fi
ko=$(find "$ROOT/lib/modules/$kver" -name 'msm.ko*' | head -n1)
[ -z "$ko" ] && ko=$(find "$ROOT/lib/modules/$kver" -name '*.ko*' | head -n1)
if [ -n "$ko" ]; then
	case $ko in *.xz) dec="xz -dc" ;; *.zst) dec="zstd -dc" ;; *.gz) dec="gzip -dc" ;; *) dec=cat ;; esac
	# grep -c, not grep -q: with pipefail, -q closes the pipe early and the decompressor's SIGPIPE fails the test
	if [ "$($dec "$ko" 2>/dev/null | grep -a -c '\.BTF')" -gt 0 ]; then pass 4.8 "$(basename "$ko") has a .BTF section"; else fail 4.8 "$(basename "$ko") has no .BTF section"; fi
else
	skip 4.8 "no msm module to look for .BTF in"
fi

# ---------------------------------------------------------------- check 5 ----
lsinitrd "$initrd_img" >"$W/initrd-list.txt" 2>&1
builtin=$ROOT/lib/modules/$kver/modules.builtin
find "$ROOT/lib/modules/$kver" -type f \( -name '*.ko' -o -name '*.ko.*' \) 2>/dev/null | sed 's|.*/||;s|\.ko.*||;s|-|_|g' | sort -u >"$W/ko-names.txt"
sed 's|.*/||;s|\.ko$||;s|-|_|g' "$builtin" 2>/dev/null | sort -u >"$W/builtin-names.txt"
sed 's|.*/||;s|\.ko.*||;s|-|_|g' <(grep -E '\.ko' "$W/initrd-list.txt" | awk '{print $NF}') | sort -u >"$W/initrd-ko.txt"
if [ "$smoke" = true ]; then
	skip 5.1 "smoke build: SP11 module list not applicable to a Fedora kernel"
else
	while read -r kind mod; do
		case $kind in '' | '#'*) continue ;; esac
		n=${mod//-/_}
		case $kind in
		early | late)
			if grep -qx "$n" "$W/ko-names.txt" "$W/builtin-names.txt"; then pass 5.1 "$mod in the kernel package"; else fail 5.1 "$mod not in the kernel package"; fi
			[ "$kind" = early ] && { if grep -qx "$n" "$W/initrd-ko.txt" || grep -qx "$n" "$W/builtin-names.txt"; then pass 5.2 "$mod early (initramfs or built in)"; else fail 5.2 "$mod not in the initramfs"; fi; } ;;
		never-early) if grep -qx "$n" "$W/initrd-ko.txt"; then fail 5.3 "$mod is in the initramfs (decision F1)"; else pass 5.3 "$mod is not in the initramfs (decision F1)"; fi ;;
		esac
	done <"$REPO/image/expected-modules.txt"
fi
# 5.5 (M4): the display chain and everything modules.dep says it needs must be in the real initramfs
# (a module that is built in needs nothing). Names are normalised (- = _). A missing one fails L0.
if [ "$smoke" != true ]; then
	python3 -I - "$ROOT/lib/modules/$kver/modules.dep" "$W/initrd-ko.txt" "$W/builtin-names.txt" "$REPO/image/expected-modules.txt" <<'PY' >"$W/initrd-deps.txt"
import re, sys
dep, ko, builtin, exp = sys.argv[1:5]
norm = lambda n: re.sub(r'\.ko(\..*)?$', '', n.rsplit('/', 1)[-1]).replace('-', '_')
deps = {}
for l in open(dep):
    p, _, d = l.partition(':')
    deps[norm(p)] = [norm(x) for x in d.split()]
inird = {l.strip() for l in open(ko)}
built = {l.strip() for l in open(builtin)}
chain = [norm(l.split()[1]) for l in open(exp) if l.split() and l.split()[0] == 'early']
missing, total = [], 0
for m in chain:
    if m in built:
        continue
    if m not in deps:
        missing.append(f"{m} (not in modules.dep)"); continue
    seen, todo = set(), [m]
    while todo:
        x = todo.pop()
        if x in seen: continue
        seen.add(x); todo += deps.get(x, [])
    for x in sorted(seen):
        total += 1
        if x not in inird and x not in built:
            missing.append(f"{x} (needed by {m})")
print(("FAIL " + "; ".join(sorted(set(missing)))) if missing else f"PASS {len(chain)} display-chain modules and their {total} module-dependency entries are in the initramfs or built in")
PY
	line=$(cat "$W/initrd-deps.txt"); case $line in PASS*) pass 5.5 "${line#PASS }" ;; *) fail 5.5 "display chain not complete in the initramfs: ${line#FAIL }" ;; esac
fi
if [ "$builder" = kiwi ]; then
	# M4: the failure capture hook is in the initramfs, with the tools and the vfat module it needs
	miss=
	for f in usr/libexec/sp11-initrd-log etc/sp11-boot-medium usr/bin/lsblk usr/bin/blkid usr/bin/gzip usr/bin/journalctl; do grep -q -E "[ /]${f}( |\$)" "$W/initrd-list.txt" || miss="$miss $f"; done
	grep -q -E 'hooks/emergency/.*60-hook-emergency|hooks/emergency/.*sp11' "$W/initrd-list.txt" || miss="$miss hooks/emergency"
	grep -q -E 'hooks/initqueue/timeout/.*sp11|hooks/initqueue/timeout/.*98-hook-timeout' "$W/initrd-list.txt" || miss="$miss hooks/initqueue/timeout"
	grep -q -E '/vfat\.ko' "$W/initrd-list.txt" || miss="$miss vfat.ko"
	[ -z "$miss" ] && pass 5.6 "initramfs has the sp11-initrd-log hooks (emergency, initqueue timeout), its tools and vfat" || fail 5.6 "initramfs lacks:$miss"
fi
if [ "$builder" = kiwi ]; then
	# D20: the four DSP images are in the initramfs with the hashes of firmware/manifest.toml; the GPU zap shader and
	# gen70500 are not (msm_open loads them at the first open)
	for lp in qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn; do
		want=$(python3 -I -c "
import sys, tomllib
m = tomllib.load(open(sys.argv[1], 'rb'))
print(next((b['sha256'] for b in m['blob'] if b.get('linux_path') == sys.argv[2]), ''))" "$REPO/firmware/manifest.toml" "$lp")
		got=$(lsinitrd "$initrd_img" -f "usr/lib/firmware/$lp" 2>/dev/null | sha256sum | cut -d' ' -f1)
		if [ -n "$want" ] && [ "$got" = "$want" ]; then pass 5.7 "initramfs has $lp, SHA-256 equals firmware/manifest.toml"; else fail 5.7 "initramfs $lp: SHA-256 ${got:0:16}... (manifest ${want:0:16}...)"; fi
	done
	if grep -q -E 'gen70500|qcdxkmsuc8380' "$W/initrd-list.txt"; then fail 5.8 "GPU zap shader or gen70500 is in the initramfs"; else pass 5.8 "GPU zap shader and gen70500 are not in the initramfs"; fi
fi
grep -E '^[-dlcbps][-rwxsStT]{9} .*plymouth' "$W/initrd-list.txt" >/dev/null && fail 5.4 "plymouth files in the initramfs" || pass 5.4 "no plymouth in the initramfs"

# ---------------------------------------------------------------- check 6 ----
python3 - "$REPO/firmware/manifest.toml" "$ROOT" "$W/rpm-files.txt" "$smoke" <<'EOF' >"$W/firmware-check.txt"
import hashlib, os, sys, tomllib
manifest, root, rpmlist, smoke = sys.argv[1:5]
m = tomllib.load(open(manifest, 'rb'))
# merged /usr: some packages (b43-openfwwf) record /lib/firmware/..., the tree walk sees /usr/lib/...
owned = set()
for l in open(rpmlist):
    l = l.strip()
    owned.add(l)
    if l.startswith('/lib/'):
        owned.add('/usr' + l)
fwdir = os.path.join(root, 'usr/lib/firmware')
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()
expected = set()
for b in m.get('blob', []):
    if b.get('phase', 1) > 1:
        continue
    lp = b['linux_path']
    if b.get('origin') == 'driverstore':
        expected.add(os.path.normpath('/usr/lib/firmware/' + lp))
        p = os.path.join(fwdir, lp)
        if smoke == 'true':
            print(f"SKIP 6.1 {lp}: smoke build has no staged firmware")
        elif not os.path.isfile(p):
            print(f"FAIL 6.1 {lp}: missing")
        elif sha(p) != b['sha256']:
            print(f"FAIL 6.1 {lp}: SHA-256 differs from the manifest")
        else:
            print(f"PASS 6.1 {lp}: present, SHA-256 matches the manifest")
    else:
        found = [p for p in (lp, lp + '.xz', lp + '.zst') if os.path.isfile(os.path.join(fwdir, p))]
        print(("PASS" if found else "FAIL") + f" 6.2 {lp}: " + (f"Fedora package file {found[0]}" if found else "linux-firmware file missing"))
extra = []
for d, _, fs in os.walk(fwdir):
    for f in fs:
        p = os.path.join(d, f)
        rel = '/' + os.path.relpath(p, root)
        if rel in owned or rel in expected:
            continue
        extra.append(rel)
print("PASS 6.3 every file under /usr/lib/firmware is owned by an RPM or in the manifest" if not extra else "FAIL 6.3 unexpected files in /usr/lib/firmware: " + ' '.join(extra[:10]))
EOF
while IFS= read -r line; do
	case $line in PASS*) npass=$((npass + 1)) ;; FAIL*) nfail=$((nfail + 1)) ;; SKIP*) nskip=$((nskip + 1)) ;; esac
	say "$line"
done <"$W/firmware-check.txt"

# ---------------------------------------------------------------- check 7 ----
# Files not owned by any RPM are ours (overlay, firmware, fstab, ...): scan them for MAC addresses.
( cd "$ROOT" && find . -xdev -type f -size -4M ! -path './usr/lib/firmware/*' ! -path './proc/*' ! -path './sys/*' | sed 's|^\.||' | sort ) >"$W/all-files.txt"
comm -23 "$W/all-files.txt" "$W/rpm-files.txt" >"$W/unowned.txt"
macs=$(cd "$ROOT" && sed 's|^/||' "$W/unowned.txt" | xargs -r -d '\n' grep -I -H -o -E '\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b' 2>/dev/null | grep -v -i -E ':(00:00:00:00:00:00|ff:ff:ff:ff:ff:ff)$' | head -n 5)
[ -z "$macs" ] && pass 7.1 "no MAC address in the $(wc -l <"$W/unowned.txt") files not owned by an RPM" || fail 7.1 "MAC-like strings in unowned files: $macs"
# only files not owned by an RPM: packaged text (the magic database mentions DriverStore) is not ours
hits=$(cd "$ROOT" && sed 's|^/||' "$W/unowned.txt" | xargs -r -d '\n' grep -IlF -e 'sp11-windows-dumps' -e 'sources/windows' -e 'DriverStore' -e 'juniormverli' 2>/dev/null | head -n 5)
[ -z "$hits" ] && pass 7.2 "no sources/windows path, DriverStore or host user name in any file not owned by an RPM" || fail 7.2 "private strings in: $hits"
# RPM-owned files that %post or the overlay changed (orchestrator follow-up of the M2 report): rpm -Va
# lists them; those whose content differs (flag 5) get the same scan as the unowned files.
say "...rpm -Va on the image (a few minutes)"
rpm --root "$ROOT" -Va >"$W/rpm-va.txt" 2>"$W/rpm-va.err"
awk '$1 ~ /^..5/ {print $NF}' "$W/rpm-va.txt" | sort -u >"$W/rpm-modified.txt"
mods=$(grep -c . "$W/rpm-modified.txt")
mac_mod=$(cd "$ROOT" && sed 's|^/||' "$W/rpm-modified.txt" | xargs -r -d '\n' grep -I -H -o -E '\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b' 2>/dev/null | grep -v -i -E ':(00:00:00:00:00:00|ff:ff:ff:ff:ff:ff)$' | head -n 5)
hits_mod=$(cd "$ROOT" && sed 's|^/||' "$W/rpm-modified.txt" | xargs -r -d '\n' grep -IlF -e 'sp11-windows-dumps' -e 'sources/windows' -e 'DriverStore' -e 'juniormverli' 2>/dev/null | head -n 5)
[ -z "$mac_mod$hits_mod" ] && pass 7.4 "no MAC address or private string in the $mods RPM-owned files whose content rpm -Va reports changed ($(tr '\n' ' ' <"$W/rpm-modified.txt" | cut -c1-200))" || fail 7.4 "private strings in modified RPM files: $mac_mod $hits_mod"
priv_iso=$(grep -rIlF -e 'sp11-windows-dumps' -e 'sources/windows' -e 'juniormverli' "$W/iso-tree" 2>/dev/null | head -n3)
[ -z "$priv_iso" ] && pass 7.3 "no private string in the ISO boot files" || fail 7.3 "private strings in ISO boot files: $priv_iso"

# ---------------------------------------------------------------- check 8 ----
svc=$ROOT/usr/lib/systemd/system/sp11-log-collector.service
[ -f "$svc" ] && pass 8.1 "sp11-log-collector.service present" || fail 8.1 "service file missing"
[ "$(readlink "$ROOT/etc/systemd/system/multi-user.target.wants/sp11-log-collector.service")" = /usr/lib/systemd/system/sp11-log-collector.service ] && pass 8.2 "enabled for multi-user.target" || fail 8.2 "not enabled for multi-user.target"
grep -q '^WantedBy=multi-user.target' "$svc" && ! grep -q -E '^(After|Requires|Wants)=.*(gdm|display-manager|graphical)' "$svc" && pass 8.3 "unit does not depend on GDM or graphical.target" || fail 8.3 "unit depends on the display manager"
[ -x "$ROOT/usr/libexec/sp11-log-collector" ] && bash -n "$ROOT/usr/libexec/sp11-log-collector" && pass 8.4 "collector script executable, syntax ok" || fail 8.4 "collector script missing, not executable or broken"
# first boot runs `preset-all` when /etc/machine-id is "uninitialized" (kiwi); the unit must be enabled by preset
grep -q -x 'enable sp11-log-collector.service' "$ROOT"/usr/lib/systemd/system-preset/80-sp11.preset 2>/dev/null && pass 8.7 "preset enables the collector (survives preset-all at first boot)" || fail 8.7 "no preset enabling sp11-log-collector.service"
if [ "$builder" = kiwi ]; then
	# D19: the display-lcd DPCD tool is in the image, byte-identical to the worker's file, and the unit starts early
	[ -x "$ROOT/usr/libexec/sp11-collect-dpcd.py" ] && cmp -s "$ROOT/usr/libexec/sp11-collect-dpcd.py" "$REPO/hardware/display-lcd/tools/collect-dpcd.py" && python3 -I -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$ROOT/usr/libexec/sp11-collect-dpcd.py" && pass 8.8 "collect-dpcd.py is in the image, executable, equal to hardware/display-lcd/tools/collect-dpcd.py" || fail 8.8 "collect-dpcd.py missing, not executable or different from the display-lcd tool"
	grep -q '^DefaultDependencies=no' "$svc" && pass 8.9 "collector unit starts without default dependencies (early)" || fail 8.9 "collector unit has default dependencies"
	# M5 (D21): session triggers, mount only per write, only the GPU speed-bin cell of the qfprom
	ok=1
	for u in sp11-log-collector-session-first.path sp11-log-collector-session-user.path; do
		[ "$(readlink "$ROOT/etc/systemd/system/multi-user.target.wants/$u")" = "/usr/lib/systemd/system/$u" ] && [ -f "$ROOT/usr/lib/systemd/system/$u" ] || { ok=0; fail 8.14 "$u missing or not enabled"; }
	done
	[ -f "$ROOT/usr/lib/systemd/system/sp11-log-collector-session@.service" ] && grep -q 'session %i' "$ROOT/usr/lib/systemd/system/sp11-log-collector-session@.service" || { ok=0; fail 8.14 "sp11-log-collector-session@.service missing"; }
	grep -q 'sp11-log-collector-session-first.path' "$ROOT/usr/lib/systemd/system-preset/80-sp11.preset" && grep -q 'session-user.path' "$ROOT/usr/lib/systemd/system-preset/80-sp11.preset" || { ok=0; fail 8.14 "session path units not in the preset (preset-all would disable them)"; }
	[ "$ok" = 1 ] && pass 8.14 "logind session triggers (path units for the first session and the first numbered user session) are installed, enabled and preset"
	ck=$ROOT/usr/libexec/sp11-log-collector
	if grep -q '^release_target()' "$ck" && grep -q 'release_target' "$ck" && awk '/^publish\(\)/,/^}/' "$ck" | grep -q 'release_target'; then pass 8.15 "collector: publish() mounts for the write and releases (sync, umount, verify) after it"; else fail 8.15 "collector does not release the target after each publish"; fi
	# the speed-bin read: one aligned 4-byte window at 0x118 (the nvmem core rejects unaligned reads), the 2-byte cell cut out of it
	if [ "$(grep -c 'dd if="$dev/nvmem"' "$ck")" = 1 ] && grep -q 'dd if="$dev/nvmem" bs=4 skip=$((0x118 / 4)) count=1' "$ck"; then pass 8.16 "collector reads the GPU speed bin with one aligned 4-byte read at 0x118 of the qfprom, nothing else (S5)"; else fail 8.16 "qfprom read is not the single aligned 4-byte window at 0x118"; fi
	# M5 device log: debugfs reads only from an allow-list. The collector's own function is run against paths: every
	# msm dpu/drm object debugfs file (crtc-*, plane-*, encoder-*, connector, dp_debug) must be refused, the known-safe ones allowed.
	dbgt=$W/debugfs-allow-test.sh
	{ echo 'shopt -s extglob'; sed -n '/^debugfs_allowed() {/,/^}/p' "$ck"; cat <<'EOT'
bad=0
for p in /sys/kernel/debug/dri/0/crtc-0/state /sys/kernel/debug/dri/0/crtc-1/state /sys/kernel/debug/dri/0/plane-3/state /sys/kernel/debug/dri/0/encoder-0/state \
	/sys/kernel/debug/dri/0/DP-1/dp_debug /sys/kernel/debug/dri/0/eDP-1/dp_debug /sys/kernel/debug/dri/0/dpu_ctl.1 /sys/kernel/debug/dri/0/crtc-0/crc/data \
	/sys/kernel/debug/dri/0/gem /sys/kernel/debug/dri/128/state /sys/kernel/debug/dri/0/../0/crtc-0/state /sys/kernel/debug/dri/0/state/crtc-0 /sys/kernel/debug/msm/foo; do
	debugfs_allowed "$p" && { echo "WRONGLY ALLOWED: $p"; bad=1; }
done
for p in /sys/kernel/debug/dri/0/state /sys/kernel/debug/dri/0/name /sys/kernel/debug/clk/clk_summary /sys/kernel/debug/devices_deferred /sys/kernel/debug/pinctrl/foo-pinctrl/pins; do
	debugfs_allowed "$p" || { echo "WRONGLY REFUSED: $p"; bad=1; }
done
debugfs_allowed /sys/class/drm/card0/status || { echo "sysfs path must not be this function's business"; bad=1; }
exit $bad
EOT
	} >"$dbgt"
	dres=$(bash "$dbgt" 2>&1) && pass 8.18 "debugfs allow-list: crtc-*, plane-*, encoder-*, connector and dp_debug files are refused, the known-safe files allowed" || fail 8.18 "debugfs allow-list: $dres"
	grep -q 'if ! debugfs_allowed "\$f"' "$ck" && ! grep -q -E 'exec cat|cat /sys/kernel/debug/dri/\*|crtc-' <(grep -v '^[[:space:]]*#' "$ck") && pass 8.19 "collector: dump_tree is gated by the allow-list, no direct read of dri/*/crtc-*" || fail 8.19 "collector: dump_tree is not gated or reads crtc-* directly"
	grep -q '/proc/asound/cards' "$ck" && grep -q 'aplay -l' "$ck" && pass 8.17 "collector records /proc/asound/cards and aplay -l" || fail 8.17 "collector lacks the sound evidence"
	# S4: the collector and the initramfs hook write only to a partition of the boot medium's disk
	ck=$ROOT/usr/libexec/sp11-log-collector; ih=$ROOT/usr/lib/dracut/modules.d/95sp11-initrd-log/sp11-initrd-log.sh
	for f in "$ck" "$ih"; do
		if grep -q 'pkname' "$f" && grep -q 'BOOT_DISK' "$f" && grep -q 'disk_has_windows\|e6d6d379-f507-44c2-a23c-238f2a3df928' "$f" && grep -q 'S4' "$f"; then pass 8.11 "$(basename "$f"): PKNAME restriction to the boot medium and the NTFS/BitLocker/MSR guard are present"; else fail 8.11 "$(basename "$f") lacks the PKNAME restriction or the Windows-disk guard (S4)"; fi
	done
	! grep -q 'live_parent_disk\|\[ -z "\$dev" \] && dev=\$cand' "$ck" "$ih" && pass 8.12 "no 'any partition labelled ...' fallback left in either script" || fail 8.12 "an 'any BOOT partition' fallback is still in a script (S4)"
	iso_vol=$(xorriso -indev "$iso" -pvd_info 2>&1 | sed -n 's/^Volume Id *: *//p' | head -n1)
	. "$ROOT/etc/sp11-boot-medium" 2>/dev/null
	[ -n "$iso_vol" ] && [ "${SP11_MEDIUM_LABEL:-}" = "$iso_vol" ] && pass 8.13 "/etc/sp11-boot-medium label '$SP11_MEDIUM_LABEL' equals the ISO volume id" || fail 8.13 "/etc/sp11-boot-medium label '${SP11_MEDIUM_LABEL:-}' differs from the ISO volume id '$iso_vol'"
	grep -q '^CAP_ESP_KIB=32768' "$ROOT/etc/sp11-log-collector.conf" && grep -q '^ESP_LABEL=BOOT' "$ROOT/etc/sp11-log-collector.conf" && pass 8.10 "collector fallback is the ESP labelled BOOT, cap 32 MiB" || fail 8.10 "collector ESP settings missing in /etc/sp11-log-collector.conf"
fi
for t in dmesg journalctl lspci lsusb dtc timeout blkid mount python3 lsmod; do
	[ -x "$ROOT/usr/bin/$t" ] || [ -x "$ROOT/usr/sbin/$t" ] || fail 8.5 "collector needs $t, not in the image"
done
for t in debug loglevel=8 ignore_loglevel; do grep -q "$t" "$ROOT/etc/default/grub" || fail 8.6 "/etc/default/grub lacks $t"; done

# ------------------------------------------------------------ extra (D9) ----
v=$(grep -s -w -E 'quiet|rhgb|splash' "$ROOT"/etc/default/grub "$ROOT"/etc/kernel/cmdline "$ROOT"/usr/lib/kernel/cmdline "$ROOT"/boot/loader/entries/*.conf 2>/dev/null | grep -v '^[^:]*:[[:space:]]*#' | head -n3)
[ -z "$v" ] && pass 9.1 "no quiet/rhgb/splash in the installed-system boot configuration" || fail 9.1 "quiet/rhgb in: $v"
if [ "$builder" = kiwi ]; then
	# kiwi: Fedora's package groups require plymouth, excluding it makes dnf5 fail; it is installed
	# but off: units masked, and (check 5.4) not in the initramfs, rd.plymouth=0 on every entry
	pm=0
	for u in start quit quit-wait read-write switch-root halt reboot poweroff kexec; do
		[ "$(readlink "$ROOT/etc/systemd/system/plymouth-$u.service")" = /dev/null ] || pm=1
	done
	[ "$pm" = 0 ] && pass 9.2 "plymouth units are masked (kiwi: the package stays installed)" || fail 9.2 "a plymouth unit is not masked"
else
	rpm --root "$ROOT" -q plymouth >/dev/null 2>&1 && fail 9.2 "plymouth is installed" || pass 9.2 "plymouth is not installed"
fi
rpm --root "$ROOT" -q qcom-firmware >/dev/null 2>&1 && pass 9.3 "qcom-firmware is installed" || fail 9.3 "qcom-firmware is not installed"
for p in pd-mapper; do rpm --root "$ROOT" -q "$p" >/dev/null 2>&1 && fail 9.4 "$p is installed (obsolete in Fedora 44)"; done

say "SUMMARY: $npass passed, $nfail failed, $nskip skipped  ($name)"
[ "$nfail" = 0 ]
