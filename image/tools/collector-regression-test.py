#!/usr/bin/env python3
"""Static guard for collector ordering, deadlines and the S4 target restriction."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
s = (root / 'image/overlay/usr/libexec/sp11-log-collector').read_text()
def body(name):
    match = re.search(r'^' + re.escape(name) + r'\(\) \{[^\n]*\n(.*?)^\}', s, re.M | re.S)
    assert match, name
    return match.group(1)
session = body('session_snapshot')
assert session.index('>"$OUT/STATUS.session-$reason"') < session.index('\tpublish') < session.index('session-$reason-loginctl.txt')
assert session.index('session-$reason-journal.txt') < session.rindex('\tpublish') < session.index('early_snapshot')
early = body('early_snapshot')
assert early.index('\tpublish') < early.index('bounded_display_set')
assert 'timeout -k 5 180 bash -c display_set' in body('bounded_display_set')
assert 'timeout -k 2 90 bash' in body('snapshot')
camera = body('camera_snapshot')
assert '[ -x "$d" ]' in camera and '/etc/sp11-log-collector.d/cameras.sh' in camera
assert camera.index('extra-cameras.txt') < camera.index('publish') < camera.index('timeout -k 2 90 bash') < camera.rindex('publish')
assert s.index('\tcamera_snapshot\n\t# fast cadence') > s.index('run)')
assert '[ "$d" = /etc/sp11-log-collector.d/cameras.sh ] && continue' in body('snapshot')
assert 'flock -w 60' in body('publish')
target = body('on_boot_disk')
assert '"$(pkname "$cand")" = "$BOOT_DISK"' in target
assert '[ "$type" = vfat ]' in target
assert 'disk_has_windows "$BOOT_DISK"' in body('find_target')
assert 'return 0' in body('disk_has_windows') and '"$rc" -eq 124' in body('disk_has_windows')
print('collector regression checks passed')

# Exercise the real selector with controlled blkid/parent responses; no mounts.
import subprocess
selector = 'on_boot_disk() {\n' + target + '}\n'
harness = r'''
BOOT_DISK=boot
pkname() { case "$1" in /dev/decoy) echo other;; *) echo boot;; esac; }
timeout() {
    case "$*" in
        *'-t LABEL=SP11LOGS'*) printf '%s\n' /dev/decoy /dev/notfat /dev/good ;;
        *'/dev/decoy'*) echo vfat ;;
        *'/dev/notfat'*) echo ext4 ;;
        *'/dev/good'*) echo vfat ;;
    esac
}
'''
checks = r'''
[ "$(on_boot_disk SP11LOGS)" = /dev/good ]
BOOT_DISK=missing
if on_boot_disk SP11LOGS; then exit 1; fi
'''
subprocess.run(['bash', '-eu', '-c', harness + selector + checks], check=True)
print('FAT and parent-disk selection checks passed')

# Run the camera registration with a harmless temporary drop-in and fake publisher.
import tempfile
with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    dropin = tmp / 'cameras.sh'
    dropin.write_text('#!/bin/bash\necho camera-evidence\n')
    dropin.chmod(0o755)
    function = 'camera_snapshot() {\n' + camera.replace('/etc/sp11-log-collector.d/cameras.sh', str(dropin)) + '}\n'
    harness = 'OUT="$1"; publish() { cp "$OUT/extra-cameras.txt" "$OUT/published-$((++count))"; }; say() { :; }; count=0\n'
    checks = 'camera_snapshot; test "$count" = 2; grep -q started "$OUT/published-1"; grep -q camera-evidence "$OUT/published-2"\n'
    subprocess.run(['bash', '-eu', '-c', harness + function + checks, '_', directory], check=True)
print('early camera publication checks passed')
