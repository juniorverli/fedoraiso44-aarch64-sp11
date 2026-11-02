#!/usr/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export SP11_TEST_TARGET=$tmp/target SP11_TEST_WORK=$tmp/work SP11_TEST_BOOT_ID=test-boot
export CAP_LOGS_KIB=4096 RESERVE_KIB=0
collector=$repo/image/overlay/usr/libexec/sp11-log-collector
printf 'first record\n' | "$collector" live-append
file=$SP11_TEST_TARGET/$SP11_TEST_BOOT_ID/kmsg-live-$SP11_TEST_BOOT_ID.txt
[ "$(cat "$file")" = 'first record' ]
[ -s "$SP11_TEST_TARGET/$SP11_TEST_BOOT_ID/STATUS.kmsg-live" ]
python3 -c 'import sys; sys.stdout.write("x" * 2200000 + "END\n")' | "$collector" live-append
[ "$(stat -c %s "$file")" -le 2097152 ]
[ "$(tail -c 4 "$file")" = END ]
[ "$(du -sk "$SP11_TEST_TARGET" | cut -f1)" -le "$CAP_LOGS_KIB" ]
[ ! -e "$file.new" ]
printf 'kmsg tail publication: PASS\n'
