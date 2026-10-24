#!/usr/bin/env bash
# Build the embedded EFI system partition image (images/efiboot.img) with
# dosfstools + mtools, without mounting anything.
#
# Replaces lorax `mkefiboot`, which loop-mounts a vfat image. The WSL2 kernel of
# the build host has no vfat driver, so that mount fails there. The result is the
# same layout (FAT, label ANACONDA, EFI/BOOT/...), plus free space for the log
# collector fallback (/EFI/sp11-logs, image/README.md D7).
#
#   mk-efiboot.sh <dir with EFI/BOOT content> <output image> <label>
set -euo pipefail
dir=${1:?dir}
img=${2:?image}
label=${3:-ANACONDA}
free_kib=${SP11_ESP_FREE_KIB:-16384}

root=$(dirname "$dir") # <dir> is .../EFI/BOOT; the image root holds EFI/
used_kib=$(du -sk --apparent-size "$dir" | cut -f1)
# FAT overhead and rounding: x1.25 + 1 MiB, then the free space for logs
size_kib=$(((used_kib * 5 / 4) + 1024 + free_kib))

rm -f "$img"
truncate -s "${size_kib}K" "$img"
mkfsargs=(-n "$label")
[ -n "${SOURCE_DATE_EPOCH:-}" ] && mkfsargs+=(-i "$(printf '%x' "$SOURCE_DATE_EPOCH")")
mkfs.vfat "${mkfsargs[@]}" "$img" >/dev/null
mmd -i "$img" ::EFI
mcopy -i "$img" -s -Q -m "$dir" ::EFI/
mdir -i "$img" -/ ::EFI >/dev/null
echo "mk-efiboot: $img ${size_kib} KiB, label $label, content from $root"
