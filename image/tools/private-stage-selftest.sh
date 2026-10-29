#!/usr/bin/env bash
# Selftest of the private build mode (image/tools/private-stage.py) and of the public-mode guards.
# Uses invented locally-administered addresses; never reads the operator's files.
#   image/tools/private-stage-selftest.sh
set -uo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
tool=$here/image/tools/private-stage.py
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
n=0 f=0
ok() { n=$((n + 1)); echo "PASS $1"; }
no() { n=$((n + 1)); f=$((f + 1)); echo "FAIL $1"; }
run() { python3 -I "$tool" "$@"; }

W=02:11:22:33:44:55 B=02:AA:BB:CC:DD:EE
printf 'WIFI_MAC=%s\nBT_MAC=%s\n' "$W" "$B" >"$t/mac.conf"
{ printf 'QCA-ATH12K-BOARD\0'; head -c 4096 /dev/zero; } >"$t/board.bin"

# --- stage
out=$(run stage --mac-conf "$t/mac.conf" --board "$t/board.bin" --out "$t/stage" 2>&1); rc=$?
[ $rc = 0 ] && ok "stage succeeds" || no "stage succeeds ($out)"
echo "$out" | grep -qiE "$W|$B|${W//:/}|${B//:/}" && no "stage output prints no value" || ok "stage output prints no value"
grep -qiE "$W|$B" "$t/stage/private-record.json" && no "stage record has no value" || ok "stage record has no value"
[ "$(stat -c %a "$t/stage/root/etc/sp11/bt-address")" = 600 ] && ok "bt-address 0600" || no "bt-address 0600"
[ "$(cat "$t/stage/root/etc/sp11/bt-address")" = "$B" ] && ok "bt-address equals source, one line" || no "bt-address equals source"
grep -qx "wifi.cloned-mac-address=$W" "$t/stage/root/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf" && ok "NM conf carries WIFI_MAC" || no "NM conf carries WIFI_MAC"
grep -qx "MACAddress=$W" "$t/stage/root/etc/systemd/network/10-sp11-wifi.link" && ok ".link carries WIFI_MAC" || no ".link carries WIFI_MAC"
cmp -s "$t/board.bin" "$t/stage/root/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin" && ok "board staged byte-identical" || no "board staged"

# --- verify on the stage as if it were the ISO root (+ a fake Fedora firmware file)
mkdir -p "$t/stage/root/usr/lib/firmware/ath12k/WCN7850/hw2.0"; : >"$t/stage/root/usr/lib/firmware/ath12k/WCN7850/hw2.0/board-2.bin.xz"
sed 's/"private": true/"private": true/' "$t/stage/private-record.json" >"$t/rec.json"
python3 -I - "$t" <<'PY'
import json, sys
t = sys.argv[1]
p = json.load(open(f"{t}/stage/private-record.json"))
json.dump({"name": "x-private", "private": p}, open(f"{t}/rec.json", "w"))
PY
run verify --root "$t/stage/root" --mac-conf "$t/mac.conf" --board "$t/board.bin" --record "$t/rec.json" >"$t/v.txt" 2>&1 && ok "verify passes on a good root" || { no "verify passes on a good root"; grep FAIL "$t/v.txt"; }
grep -qiE "$W|$B" "$t/v.txt" && no "verify output prints no value" || ok "verify output prints no value"

# --- negative cases
cp -a "$t/stage" "$t/bad"
printf '%s\n' 02:00:00:00:00:99 >"$t/bad/root/etc/sp11/bt-address"
run verify --root "$t/bad/root" --mac-conf "$t/mac.conf" >/dev/null 2>&1 && no "verify catches a wrong bt-address" || ok "verify catches a wrong bt-address"
cp -a "$t/stage" "$t/bad2"; chmod 644 "$t/bad2/root/etc/sp11/bt-address"
run verify --root "$t/bad2/root" --mac-conf "$t/mac.conf" >/dev/null 2>&1 && no "verify catches mode 0644 on bt-address" || ok "verify catches mode 0644 on bt-address"
cp -a "$t/stage" "$t/bad3"; rm "$t/bad3/root/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin"
run verify --root "$t/bad3/root" --mac-conf "$t/mac.conf" >/dev/null 2>&1 && no "verify catches a missing board file" || ok "verify catches a missing board file"
printf '{"name":"x","note":"%s"}' "${W,,}" >"$t/leak.json"
run verify --root "$t/stage/root" --mac-conf "$t/mac.conf" --record "$t/leak.json" >/dev/null 2>&1 && no "verify catches a value in the JSON record" || ok "verify catches a value in the JSON record"
run leaks --mac-conf "$t/mac.conf" "$t/leak.json" >/dev/null 2>&1 && no "leaks detects a lower-case address in JSON" || ok "leaks detects a lower-case address in JSON"
run leaks --mac-conf "$t/mac.conf" "$t/rec.json" >/dev/null 2>&1 && ok "leaks passes a hash-only record" || no "leaks passes a hash-only record"
printf '{"x":"%s"}' "${B//:/}" >"$t/leak2.json"
run leaks --mac-conf "$t/mac.conf" "$t/leak2.json" >/dev/null 2>&1 && no "leaks detects the compact form" || ok "leaks detects the compact form"

# --- stage refusals
run stage --mac-conf "$t/mac.conf" --board "$t/none.bin" --out "$t/s2" >"$t/e.txt" 2>&1; rc=$?
[ $rc = 6 ] && grep -q 'board file missing' "$t/e.txt" && ok "missing board file fails with a clear message" || no "missing board file fails clearly"
printf 'NOTBOARD' >"$t/junk.bin"
run stage --mac-conf "$t/mac.conf" --board "$t/junk.bin" --out "$t/s2" >/dev/null 2>&1 && no "bad board magic refused" || ok "bad board magic refused"
run stage --mac-conf "$t/mac.conf" --board "$t/board.bin" --board-sha256 0000 --out "$t/s2" >/dev/null 2>&1 && no "pinned hash mismatch refused" || ok "pinned hash mismatch refused"
printf 'WIFI_MAC=00:00:00:00:00:00\nBT_MAC=%s\n' "$B" >"$t/zero.conf"
run stage --mac-conf "$t/zero.conf" --board "$t/board.bin" --out "$t/s2" >/dev/null 2>&1 && no "sentinel address refused" || ok "sentinel address refused"
printf 'WIFI_MAC=%s\n' "$W" >"$t/half.conf"
run stage --mac-conf "$t/half.conf" --board "$t/board.bin" --out "$t/s2" >/dev/null 2>&1 && no "missing BT_MAC refused" || ok "missing BT_MAC refused"
run stage --mac-conf "$t/none.conf" --board "$t/board.bin" --out "$t/s2" >/dev/null 2>&1 && no "missing source refused" || ok "missing source refused"

# --- repo-clean
mkdir -p "$t/repo" && echo "nothing here" >"$t/repo/a.md" && run repo-clean --mac-conf "$t/mac.conf" --repo "$t/repo" >/dev/null 2>&1 && ok "repo-clean passes a clean tree" || no "repo-clean passes a clean tree"
echo "addr $B" >"$t/repo/b.md"
run repo-clean --mac-conf "$t/mac.conf" --repo "$t/repo" >/dev/null 2>&1 && no "repo-clean catches an address" || ok "repo-clean catches an address"

# --- public mode stays the default and its assertions stay
grep -q '^private=0' "$here/scripts/image-build.sh" && ok "image-build.sh defaults to public" || no "image-build.sh defaults to public"
grep -q "7.5 \"no operator Bluetooth address input" "$here/scripts/image-test-static.sh" && ok "L0 public 7.5 assertion retained" || no "L0 public 7.5 retained"

echo "SELFTEST: $((n - f)) passed, $f failed"
[ "$f" = 0 ]
