#!/usr/bin/env bash
# Small hybrid ISO with the same layout as the kiwi ISO (ISO9660 + appended FAT32 ESP as GPT partition 2, direct GRUB) and a
# rendered M14 grub.cfg, for image/tools/grub_logic_test.py. No kernel: the logic test stops at the echo lines.
#   make-grub-test-iso.sh ESP_IMAGE GRUB_CFG OUT_ISO      (inside the container; ESP_IMAGE = the ESP of any SP11 ISO)
set -euo pipefail
esp=$1 cfg=$2 out=$3
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
cp "$esp" "$t/esp.img"
python3 - "$t/grubenv" <<'PY'
import sys
h = "# GRUB Environment Block\n"
open(sys.argv[1], "wb").write((h + "#" * (1024 - len(h))).encode())
PY
mcopy -o -i "$t/esp.img" "$t/grubenv" ::EFI/BOOT/grubenv
mkdir -p "$t/tree/boot/grub2"
: >"$t/tree/boot/0x8944831c"
cp "$cfg" "$t/tree/boot/grub2/grub.cfg"
xorriso -as mkisofs -iso-level 3 -V SP11-GRUB-TEST -o "$out" -e --interval:appended_partition_2:all:: -no-emul-boot -appended_part_as_gpt \
	-append_partition 2 0xef "$t/esp.img" "$t/tree" >"$t/xorriso.txt" 2>&1 || { tail -5 "$t/xorriso.txt" >&2; exit 1; }
