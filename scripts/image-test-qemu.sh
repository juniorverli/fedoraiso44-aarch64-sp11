#!/usr/bin/env bash
# L1 emulated boot of an SP11 ISO (decision D10, image/README.md "L1 emulated boot").
#
#   scripts/image-test-qemu.sh [ISO | NAME] [--timeout-min N] [--mem MiB] [--smp N] [--cpu MODEL]
#
# QEMU system emulation, machine virt, TCG (the WSL2 host has no /dev/kvm), edk2 firmware,
# the ISO attached as a raw USB disk, a second small FAT disk labelled SP11LOGS, serial
# console on a pty. It selects the non-default "VM test (no devicetree)" GRUB entry.
# Pass: GRUB menu lists every entry, GDM starts, /sys/kernel/btf/vmlinux exists, the log
# collector wrote a complete <boot-id>/ to SP11LOGS, no unit failed outside the allow-list.
#
# CPU model: neoverse-n1 by default. Reason (Inference): the X1P64100 is a 64-bit Armv8.x
# core without SVE as far as the project knows (not verified here, no CPU feature data in
# sources/); of QEMU's TCG models, neoverse-n1 (Armv8.2-A: LSE atomics, dot product, fp16,
# crypto, no SVE, no pointer-auth/MTE surprises) is the closest, and -cpu max would hide
# problems behind features this SoC may not have and slow TCG down. Override with --cpu.
#
# Slow: TCG with 8 threads needs 30-90 min for a GNOME boot. Run unattended.
# Refuses to start while out/.kernel-build.lock is held (RAM). Re-executes itself in the
# container of scripts/image-container.sh. Report: out/iso/<name>.l1.txt (+ .l1.json),
# logs read back from the SP11LOGS disk: out/image-work/l1-<name>/collected/.
set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [ "${SP11_OUT:-}" = "" ] || [ ! -d /sp11 ]; then
	out=$(readlink -f "$here/out")
	if ! flock -n "$out/.kernel-build.lock" true 2>/dev/null; then
		echo "image-test-qemu: $out/.kernel-build.lock is held (kernel build running); not starting QEMU" >&2
		exit 3
	fi
	# shellcheck source=kernel-common.sh
	. "$here/scripts/kernel-common.sh"
	read -r h src < <(kernel_headroom)
	min=${SP11_MIN_HEADROOM_GIB:-30}
	echo "image-test-qemu: disk headroom $((h / KERNEL_GIB)) GiB [$src], need >= $min GiB"
	if ((h < min * KERNEL_GIB)); then
		echo "image-test-qemu: REFUSED: headroom $((h / KERNEL_GIB)) GiB < $min GiB [$src]" >&2
		exit 4
	fi
	exec env SP11_DOCKER_MEMORY="${SP11_DOCKER_MEMORY:-7g}" "$here/scripts/image-container.sh" run /sp11/scripts/image-test-qemu.sh "$@"
fi
OUT=$SP11_OUT

iso= timeout_min=150 mem=4096 smp=8 cpu=neoverse-n1
while [ $# -gt 0 ]; do
	case $1 in
	--timeout-min) timeout_min=${2:?}; shift ;;
	--mem) mem=${2:?}; shift ;;
	--smp) smp=${2:?}; shift ;;
	--cpu) cpu=${2:?}; shift ;;
	*) iso=$1 ;;
	esac
	shift
done
if [ -z "$iso" ]; then
	iso=$(ls -t "$OUT"/iso/*.iso 2>/dev/null | head -n1)
elif [ -f "$iso" ]; then
	:
elif [ -f "$OUT/iso/$iso" ]; then
	iso=$OUT/iso/$iso
else
	iso=$OUT/iso/$iso.iso
fi
[ -f "$iso" ] || { echo "image-test-qemu: no ISO" >&2; exit 2; }
iso=$(readlink -f "$iso")
name=$(basename "$iso" .iso)
W=$OUT/image-work/l1-$name
mkdir -p "$W"

# the second disk: FAT labelled SP11LOGS, like the partition the operator creates on the stick
logs=$W/sp11logs.img
rm -f "$logs"
truncate -s 128M "$logs"
mkfs.vfat -n SP11LOGS "$logs" >/dev/null

python3 -I /sp11/image/tools/qemu_boot_test.py \
	--iso "$iso" --logs "$logs" --work "$W" --report "$OUT/iso/$name.l1.json" \
	--cpu "$cpu" --smp "$smp" --mem "$mem" --timeout-min "$timeout_min" \
	--allow /sp11/image/l1-allowed-failed-units.txt 2>&1 | tee "$OUT/iso/$name.l1.txt"
exit "${PIPESTATUS[0]}"
