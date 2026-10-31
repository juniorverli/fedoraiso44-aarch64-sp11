#!/usr/bin/env bash
# NOTE (M15): written for the M14 menu2 ISOs. The M15 menu names DTBs m15* that an M14 ISO does not carry, so this tool is NOT usable for M15; a build needs the kernel RPMs.
# Patch an existing SP11 kiwi ISO with the menu2 grub.cfg WITHOUT a kiwi rebuild (image/README.md, "menu2 patched test ISO").
#   make-menu2-iso.sh BASE_ISO OUT_ISO WORKDIR SNAPSHOT      (inside the container of scripts/image-container.sh; /sp11 is the repository)
# SNAPSHOT = directory with `git archive HEAD` of the repository the BASE ISO was built from (made on the host, the container has no git
# worktree); L0 judges the installed Linux side of the patched ISO against it.
# 1. renders image/kiwi/overlay/grub-arm.cfg.iso-template with the values of the base ISO's own /boot/grub2/grub.cfg;
# 2. grub2-script-check and check-m8-menu.py on the result;
# 3. xorriso -indev BASE -outdev OUT -boot_image any replay -map grub.cfg /boot/grub2/grub.cfg (nothing else changes), implantisomd5;
# 4. proves preservation: partition 2 (ESP) image hash, tree diff (only grub.cfg), El Torito and system area reports, partition table sizes.
# Output: OUT_ISO and WORKDIR/preservation.txt. Only the sha256 and PASS/FAIL lines are printed.
set -euo pipefail
base=$1 out=$2 w=$3 snap=${4:?snapshot directory}
[ -d "$snap/image" ] || { echo "snapshot $snap has no image/"; exit 1; }
repo=/sp11
mkdir -p "$w"; cd "$w"
rm -f "$out"
xorriso -osirrox on -indev "$base" -extract /boot/grub2/grub.cfg "$w/base.grub.cfg" >/dev/null 2>&1
python3 -I "$repo/image/tools/render-grub-cfg.py" "$repo/image/kiwi/overlay/grub-arm.cfg.iso-template" "$w/base.grub.cfg" "$w/grub.cfg"
grub2-script-check "$w/grub.cfg"
python3 -I "$repo/image/tools/check-m8-menu.py" "$w/grub.cfg"
if grep -v '^[[:space:]]*#' "$w/grub.cfg" | grep -E -q '\b(save_env|load_env|grub2?-editenv)\b|\b(quiet|rhgb|splash)\b'; then echo "FAIL: save_env/load_env/editenv or forbidden boot word in the patched grub.cfg"; exit 1; fi
xorriso -indev "$base" -outdev "$out" -boot_image any replay -map "$w/grub.cfg" /boot/grub2/grub.cfg -commit >"$w/xorriso-patch.txt" 2>&1 || { tail -5 "$w/xorriso-patch.txt"; exit 1; }
implantisomd5 --force --supported-iso "$out" >"$w/implant.txt" 2>&1
: >"$w/preservation.txt"
rec() { echo "$*" | tee -a "$w/preservation.txt"; }
part2() { # sha256 of the content of GPT partition 2 and its size in sectors
	local f=$1 first last
	first=$(sgdisk -i 2 "$f" | sed -n 's/^First sector: \([0-9]*\).*/\1/p'); last=$(sgdisk -i 2 "$f" | sed -n 's/^Last sector: \([0-9]*\).*/\1/p')
	echo "$((last - first + 1)) sectors $(dd if="$f" bs=512 skip="$first" count=$((last - first + 1)) status=none | sha256sum | cut -d' ' -f1)"
}
a=$(part2 "$base"); b=$(part2 "$out")
[ "$a" = "$b" ] && rec "PASS partition 2 (ESP) image identical: $a" || rec "FAIL partition 2 differs: $a vs $b"
# tree: loop-mount both, diff -rq
mkdir -p "$w/m1" "$w/m2"
mount -o loop,ro "$base" "$w/m1"; mount -o loop,ro "$out" "$w/m2"
diff -rq "$w/m1" "$w/m2" >"$w/tree-diff.txt" 2>&1 || true
n=$(wc -l <"$w/tree-diff.txt")
if [ "$n" = 1 ] && grep -q "boot/grub2/grub.cfg differ" "$w/tree-diff.txt"; then rec "PASS tree: exactly one file differs, boot/grub2/grub.cfg"; else rec "FAIL tree diff: $n lines ($(head -n 3 "$w/tree-diff.txt" | tr '\n' ';'))"; fi
umount "$w/m1" "$w/m2"
norm() { # the reports without the values that must move: ISO size, ESP position (grub.cfg grew), random GPT GUIDs
	xorriso -indev "$1" -report_el_torito plain -report_system_area plain 2>/dev/null | grep -v -E '^(Drive current|Media (current|status|summary)|Volume id|Boot record|-indev|ISO image size|MBR partition|GPT )' | sed -E '/^El Torito boot img/s/[0-9]+$/LBA/'
}
cmp -s <(norm "$base") <(norm "$out") && rec "PASS El Torito and system area reports identical (type, platform, emulation, load size, sector counts; only the ESP position, ISO size and random GPT GUIDs move)" || rec "FAIL El Torito/system area reports differ"
lba=$(xorriso -indev "$out" -report_el_torito plain 2>/dev/null | sed -n 's/^El Torito boot img :.* \([0-9]*\)$/\1/p' | head -n1)
st=$(sgdisk -i 2 "$out" | sed -n 's/^First sector: \([0-9]*\).*/\1/p')
[ $((lba * 4)) = "$st" ] && rec "PASS El Torito boot image LBA $lba points at the start of GPT partition 2 ($st)" || rec "FAIL El Torito LBA $lba does not match partition 2 start $st"
tbl() { sgdisk -p "$1" | sed -n '/^Number/,$p' | awk '{print $1, $4 $5, $6, $7}'; }
[ "$(tbl "$base" | awk '{print $1,$2}')" = "$(tbl "$out" | awk '{print $1,$2}')" ] && rec "PASS GPT: same partitions and sizes" || rec "FAIL GPT differs"
for f in "$base" "$out"; do xorriso -indev "$f" -report_el_torito as_mkisofs 2>/dev/null | grep -E "^-(e|no-emul-boot|append_partition|partition_offset|appended_part_as_gpt|iso_mbr_part_type|boot-catalog-hide|-protective-msdos-label|V) " | sed -E "s|--interval:local_fs:[^ ]*|IV|;s|--interval:appended_partition_2_start_[0-9]+s|APP2|" >"$w/mkisofs-$(basename "$f").txt"; done
cmp -s "$w/mkisofs-$(basename "$base").txt" "$w/mkisofs-$(basename "$out").txt" && rec "PASS El Torito as_mkisofs report identical (boot image = appended partition 2, no-emul-boot, GPT)" || rec "FAIL as_mkisofs report differs"
sha=$(sha256sum "$out" | cut -d' ' -f1)
rec "iso sha256 $sha"
# build record: the base record with the menu2 facts (L0 reads it); patched_from names the base like the menu1 record did
python3 -I - "${base%.iso}.json" "${out%.iso}.json" "$w/grub.cfg" "$out" "$sha" "$base" "$snap" <<'PY'
import json, os, re, sys
src, dst, cfgp, iso, sha, base, snap = sys.argv[1:8]
d = json.load(open(src))
cfg = open(cfgp).read()
entries = []
for m in re.finditer(r"^[ \t]*menuentry '([^']*)'[^\n]*\{(.*?)^[ \t]*\}", cfg, re.S | re.M):
    lin = re.search(r"^\s*linux \S+ (.*)$", m.group(2), re.M)
    entries.append({"title": m.group(1), "linux_args": lin.group(1).strip() if lin else None, "devicetree": bool(re.search(r"^\s*devicetree ", m.group(2), re.M))})
d.update({"name": os.path.basename(iso)[:-4], "iso_sha256": sha, "iso_size": os.path.getsize(iso), "grub_entries": entries,
          "menu": "line 1 main entry SP11 debug (write-free: GRUB reads the environment block, never writes; m14 or m14-safe, all test arguments inline); line 2 safe (m14-safe DTB, top level); line 3 submenu 'Recovery and tests' (8 entries: bisect A and B first)"})
d["diagnostic_args_reason"]["bisect-a"] = "menu2 bisect A: m14.dtb with the safe entry arguments, static line (DTB content versus command line)"
d["diagnostic_args_reason"]["bisect-b"] = "menu2 bisect B: m14-safe.dtb with the main entry arguments with fixed values, static line (command line versus DTB)"
d["rotors"]["gpu_state"] = "sp11_gpu_state in EFI/BOOT/grubenv of the ESP: written by Linux only (testing, ok, failed); GRUB only reads it and picks m14-safe on testing/failed. NOT advancing in this patched ISO (squashfs is menu1)"
d["patched_from"] = {"name": os.path.basename(base)[:-4], "iso_sha256": json.load(open(src))["iso_sha256"],
                     "replaced": ["/boot/grub2/grub.cfg"],
                     "method": "xorriso -indev OLD -outdev NEW -boot_image any replay -map new.grub.cfg /boot/grub2/grub.cfg; not a fresh compose; implantisomd5 --force --supported-iso (same as the build); image/tools/make-menu2-iso.sh",
                     "kernel_initrd_dtb_esp": "byte-identical (tree diff has exactly one file; partition 2 image hash identical)"}
d["menu2_patch"] = {"linux_side_repo": snap, "note": "the squashfs is the menu1/M14 Linux side: GPU state and CDSP rotor do not advance in this ISO (Linux writes are the new design); L0 judges the installed scripts against this snapshot"}
json.dump(d, open(dst, "w"), indent=2)
PY
grep -q '^FAIL' "$w/preservation.txt" && exit 1 || exit 0
