#!/usr/bin/env bash
# Compare the Wi-Fi station address the device reported with the factory address recorded from
# Windows, without printing or storing either address (S5).
#
#   hardware/wifi/tools/check-mac.sh <extra-wifi.txt of one boot in out/device-logs/...>
#
# The collector prints "mac_sha256_16=<16 hex>" (lower-case address, sha256, first 16 hex).
# This script hashes WIFI_MAC from sources/windows/live-inventory/sp11-mac.conf the same way
# and prints only MATCH / DIFFERENT / the address-assignment type. Run it locally; the result
# (not the address) may go into evidence.
set -euo pipefail
log=${1:?usage: check-mac.sh extra-wifi.txt}
here=$(cd "$(dirname "$0")/../../.." && pwd)
conf="$here/sources/windows/live-inventory/sp11-mac.conf"
want=$(sed -n 's/^WIFI_MAC=//p' "$conf" | tr -d ':- \r' | tr 'A-F' 'a-f' | sed -E 's/(..)/\1:/g; s/:$//')
[ -n "$want" ] || { echo "no WIFI_MAC in $conf"; exit 2; }
want_h=$(printf '%s' "$want" | sha256sum | cut -c1-16)
got_h=$(sed -n 's/.* mac_sha256_16=\([0-9a-f]\{16\}\).*/\1/p' "$log" | head -1)
[ -n "$got_h" ] || { echo "no mac_sha256_16 line in $log"; exit 2; }
if [ "$want_h" = "$got_h" ]; then echo "MAC: MATCH (device address equals the Windows factory address)"; else echo "MAC: DIFFERENT"; fi
sed -n 's/.*addr_assign_type=\([0-9]\).*/addr_assign_type=\1 (0 = permanent from hardware, 1 = random, 2 = stolen, 3 = set by userspace)/p' "$log" | head -1
