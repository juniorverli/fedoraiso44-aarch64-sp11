#!/usr/bin/env bash
# Tests image/tools/qemu_boot_test.py against a fake QEMU (seconds, no emulation).
#   scripts/image-container.sh run /sp11/image/tools/qemu_driver_selftest.sh
set -euo pipefail
W=/out/image-work/driver-selftest
rm -rf "$W"; mkdir -p "$W/bin"
cp /sp11/image/tools/fake_qemu.py "$W/bin/qemu-system-aarch64"; chmod +x "$W/bin/qemu-system-aarch64"
truncate -s 16M "$W/logs.img"; mkfs.vfat -n SP11LOGS "$W/logs.img" >/dev/null
truncate -s 1M "$W/fake.iso"
PATH="$W/bin:$PATH" python3 -I /sp11/image/tools/qemu_boot_test.py --iso "$W/fake.iso" --logs "$W/logs.img" \
	--work "$W/work" --report "$W/report.json" --timeout-min 2 --stall-min 1 --poll-sec 3 --no-display-files
