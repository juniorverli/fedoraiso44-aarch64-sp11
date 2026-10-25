#!/usr/bin/env bash
# A fake Windows disk for the S4 test: GPT with four partitions, none of which the image may ever
# touch. Called by scripts/image-test-qemu.sh --decoy; run inside the container.
#   make-decoy-disk.sh OUT.img
#   p1 FAT32 label BOOT      (EFI system type: what a naive "any partition labelled BOOT" would pick)
#   p2 FAT32 label SP11LOGS  (the other label the collector looks for)
#   p3 NTFS  label WINDOWS   (Microsoft basic data)
#   p4 Microsoft reserved    (MSR, no file system)
set -euo pipefail
img=${1:?usage: make-decoy-disk.sh OUT.img}
rm -f "$img"
truncate -s 160M "$img"
sgdisk -Z "$img" >/dev/null
sgdisk -n 1:2048:+32M -t 1:ef00 -c 1:"EFI system partition" \
	-n 2:0:+32M -t 2:0700 -c 2:"logs" \
	-n 3:0:+48M -t 3:0700 -c 3:"Basic data partition" \
	-n 4:0:+16M -t 4:0c01 -c 4:"Microsoft reserved partition" "$img" >/dev/null
fs() { # fs N MKFS-COMMAND...: build a file system image for partition N and write it into the disk
	local n=$1 start size f
	shift
	start=$(sgdisk -i "$n" "$img" | awk '/First sector/{print $3}')
	size=$(sgdisk -i "$n" "$img" | awk '/Partition size/{print $3}')
	f=$(mktemp)
	truncate -s $((size * 512)) "$f"
	"$@" "$f" >/dev/null 2>&1
	dd if="$f" of="$img" bs=512 seek="$start" conv=notrunc status=none
	rm -f "$f"
}
fs 1 mkfs.vfat -F 32 -n BOOT
fs 2 mkfs.vfat -F 32 -n SP11LOGS
fs 3 mkntfs -F -Q -L WINDOWS
echo "decoy disk $img: $(sgdisk -p "$img" | tail -n 4 | tr -s ' ' | tr '\n' '|')"
