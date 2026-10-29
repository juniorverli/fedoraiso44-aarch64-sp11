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

# Regression: early session STATUS can replace the full snapshot's target field.
# Prove the actual destination using independent GPT/FAT fixtures.
truncate -s 80M "$W/boot.img"
sgdisk -o -n 2:2048:+64M -t 2:ef00 "$W/boot.img" >"$W/gpt-fixture.txt"
mkfs.fat -C -F 32 -s 1 -n BOOT "$W/esp.img" 65536 >/dev/null
dd if="$W/esp.img" of="$W/boot.img" bs=1M seek=1 conv=notrunc status=none
python3 -I - "$W/boot.img" "$W/logs.img" "$W/esp.img" <<'PY'
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('qemu_target_test', '/sp11/image/tools/qemu_boot_test.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
boot, logs, esp = sys.argv[1:]
image = boot + '@@1048576'
q.LOGROOT = 'EFI/sp11-logs'
for name, source, boot_image, status, want in (
    ('early session STATUS', image, boot, 'cycle: 0 (early/fast display snapshot, session first)\n', True),
    ('full STATUS', image, boot, 'target: esp\n', True),
    ('wrong disk', image, logs, '', False),
    ('wrong GPT offset', boot + '@@0', boot, '', False),
    ('contradictory target', image, boot, 'target: logs\n', False),
):
    got, detail = q.verify_log_target(source, boot_image, True, status)
    assert got is want, (name, detail)
    print('PASS target fixture:', name)
q.LOGROOT = 'other-directory'
assert not q.verify_log_target(image, boot, True, '')[0]
print('PASS target fixture: wrong ESP log directory')
q.LOGROOT = ''
assert q.verify_log_target(logs, boot, False, 'target: logs\n')[0]
assert not q.verify_log_target(esp, boot, False, 'target: logs\n')[0]
assert not q.verify_log_target(image, boot, False, 'target: logs\n')[0]
print('PASS target fixtures: SP11LOGS label accepted, wrong label and offset rejected')

# A nonexistent journal unit glob is ENODATA, not an installed-helper failure.
# Require independent VM/controller/journal evidence and reject other failures.
touch = '\n'.join(p + '\n  ABSENT' for p in (
    '/sys/firmware/devicetree/base/soc@0/geniqup@ac0000',
    '/sys/firmware/devicetree/base/soc@0/geniqup@ac0000/spi@a88000')) + '\n'
base = ('<capture failed: exit 1>\n', '<no device names>\n', touch,
        'debug sp11.entry=vmtest', 'systemd[1]: Started gdm.service\n')
assert q.touch_userspace_captures(*base)[0]
print('PASS capture fixture: evidenced VM without iptsd instance')
for name, index, value in (
    ('device entry', 3, 'debug sp11.entry=debug'),
    ('controller evidence missing', 2, ''),
    ('boot journal missing', 4, ''),
    ('instance exists', 4, base[4] + 'systemd[1]: Started iptsd@dev-hidraw0.service\n'),
    ('daemon exists', 4, base[4] + 'iptsd[42]: started\n'),
    ('other command failure', 0, '<capture failed: exit 2>\n'),
    ('capture unavailable', 0, '<capture unavailable>\n'),
    ('input capture failure', 1, '<capture failed: exit 1>\n'),
    ('input properties leaked', 1, 'Kernel: /dev/input/event0\n'),
    ('address leaked', 1, ':'.join(['12', '34', '56', '78', '9a', 'bc']) + '\n'),
):
    bad = list(base); bad[index] = value
    assert not q.touch_userspace_captures(*bad)[0], name
    print('PASS negative capture fixture:', name)
assert q.touch_userspace_captures('iptsd started\n', 'Touch\n', '', '', '')[0]
print('PASS capture fixture: nonempty iptsd journal and device name')
PY
