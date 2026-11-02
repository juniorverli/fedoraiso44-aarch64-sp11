#!/usr/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export SP11_TEST_TARGET=$tmp/target SP11_TEST_WORK=$tmp/work SP11_TEST_BOOT_ID=test-boot
export CAP_LOGS_KIB=4096 RESERVE_KIB=0
collector=$repo/image/overlay/usr/libexec/sp11-log-collector
unit=$repo/image/overlay/usr/lib/systemd/system/sp11-kmsg-tail.service
tailer=$repo/image/overlay/usr/libexec/sp11-kmsg-tail
[ "$(grep -c '^ConditionKernelCommandLine=' "$unit")" -eq 1 ]
grep -qx 'ConditionKernelCommandLine=sp11.entry=debug' "$unit"
grep -qx 'BATCH_SIZE = 256 \* 1024' "$tailer"
grep -qx 'INTERVAL = 10' "$tailer"
printf 'first record\n' | "$collector" live-append
file=$SP11_TEST_TARGET/$SP11_TEST_BOOT_ID/kmsg-live-$SP11_TEST_BOOT_ID.txt
[ "$(cat "$file")" = 'first record' ]
[ -s "$SP11_TEST_TARGET/$SP11_TEST_BOOT_ID/STATUS.kmsg-live" ]
python3 -c 'import sys; sys.stdout.write("x" * 2200000 + "END\n")' | "$collector" live-append
[ "$(stat -c %s "$file")" -le 2097152 ]
[ "$(tail -c 4 "$file")" = END ]
[ "$(du -sk "$SP11_TEST_TARGET" | cut -f1)" -le "$CAP_LOGS_KIB" ]
[ ! -e "$file.new" ]
# A busy snapshot lock must make live publication return promptly without writes.
exec 9>"$SP11_TEST_WORK.lock"
flock -x 9
if printf 'blocked record\n' | timeout 5 "$collector" live-append; then
    printf 'live publication unexpectedly acquired the lock\n' >&2
    exit 1
else
    rc=$?
    [ "$rc" -ne 124 ]
fi
flock -u 9
! grep -q 'blocked record' "$file"
printf 'kmsg tail publication: PASS\n'
python3 -I "$repo/image/tools/kmsg-urgent-selftest.py" "$tailer"
