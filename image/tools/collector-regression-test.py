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
