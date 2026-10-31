#!/usr/bin/bash
# Fixture tests for the Wi-Fi identity experiment (collector/identity.sh and
# userspace/sp11-wifi-identity). Fake sysfs and fake tools only; the addresses below are
# synthetic and exist only in this test. Run: hardware/wifi/tests/identity-test.sh
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

HW=3c:aa:bb:cc:dd:01 # what the fake firmware reports
INJ=02:11:22:33:44:55 # what a private-mode copy would set
h16() { printf '%s' "$1" | tr 'A-F' 'a-f' | sha256sum | cut -c1-16; }
ADDRS=("$HW" "${HW^^}" "${HW//:/}" "${HW^^//:/}" "${HW//:/-}" "$INJ" "${INJ^^}" "${INJ//:/}")

mkroot() { # $1 dir, $2 perm, $3 current, $4 assign_type, $5 cmdline
	local r=$1
	mkdir -p "$r/sys/class/ieee80211/phy0/device/net/wlP4p1s0" "$r/sys/class/net/wlP4p1s0" "$r/proc" "$r/usr/share/sp11" "$r/run/sp11" "$r/etc"
	printf '%s\n' "$2" >"$r/sys/class/ieee80211/phy0/macaddress"
	printf '%s\n' "$3" >"$r/sys/class/net/wlP4p1s0/address"
	printf '%s\n' "$4" >"$r/sys/class/net/wlP4p1s0/addr_assign_type"
	printf '%s\n' "$5" >"$r/proc/cmdline"
	echo "123.45 100.0" >"$r/proc/uptime"
}
mkbin() { # fake tools; $1 dir, perm and current via env at call time
	local b=$1
	mkdir -p "$b"
	cat >"$b/ethtool" <<EOT
#!/bin/sh
echo "Permanent address: $HW"
EOT
	cat >"$b/ip" <<EOT
#!/bin/sh
echo "3: wlP4p1s0: <BROADCAST> mtu 1500 link/ether $INJ brd ff:ff:ff:ff:ff:ff permaddr $HW"
EOT
	cat >"$b/iw" <<EOT
#!/bin/sh
printf 'phy#0\n\tInterface wlP4p1s0\n\t\tifindex 3\n\t\taddr %s\n\t\ttype managed\n' "\${FAKE_IW_ADDR:-$INJ}"
EOT
	cat >"$b/dmesg" <<EOT
#!/bin/sh
echo "[ 10.1] ath12k_wifi7_pci 0004:01:00.0: Hardware name: wcn7850 hw2.0"
echo "[ 10.2] ath12k_wifi7_pci 0004:01:00.0: mac address $HW from firmware"
echo "[ 10.3] ath12k_wifi7_pci 0004:01:00.0: invalid mac check skipped"
EOT
	cat >"$b/systemd-hwdb" <<'EOT'
#!/bin/sh
case "$2" in OUI:3CAABB) echo "ID_OUI_FROM_DATABASE=Fake Vendor Inc" ;; *) exit 1 ;; esac
EOT
	chmod +x "$b"/*
}
run() { # $1 root; extra env via caller; run as the real collector does (sourced in a subshell)
	PATH="$tmp/bin:$PATH" SP11_ID_ROOT=$1 SP11_ID_ALLOW_NONROOT=1 timeout 20 bash -c ". '$here/collector/identity.sh'" 2>&1
}
noaddr() { # $1 file: no fake address, in any spelling, appears
	local a
	for a in "${ADDRS[@]}"; do grep -qiF -- "$a" "$1" && return 1; done
	return 0
}

mkbin "$tmp/bin"

# 1. private, inject: injected current address, hardware permanent address
r=$tmp/r1; mkroot "$r" "$HW" "$INJ" 3 "root=live sp11.entry=debug"
echo private >"$r/usr/share/sp11/image-mode"
printf 'wifi=%s\nbt=%s\n' "$(h16 "$HW")" "0123456789abcdef" >"$r/usr/share/sp11/identity-ref.sha256"; chmod 600 "$r/usr/share/sp11/identity-ref.sha256"
run "$r" >"$tmp/o1"
check "private/inject: switch=inject, image_mode=private" "grep -q 'image_mode=private identity_switch=inject' $tmp/o1"
check "private/inject: permanent hash printed (16 hex)" "grep -q 'wifi.permanent.*sha256_16=$(h16 "$HW") ' $tmp/o1"
check "private/inject: permanent MATCH, current NO MATCH" "grep -q 'ref_match.permanent=MATCH' $tmp/o1 && grep -q 'ref_match.current=NO MATCH' $tmp/o1"
check "private/inject: current differs from permanent, type 3 set-by-userspace" "grep -q 'current_equals_permanent=no' $tmp/o1 && grep -q 'addr_assign_type=3(set-by-userspace)' $tmp/o1"
check "oui class registered, no vendor name" "grep -q 'oui_class=registered' $tmp/o1 && ! grep -qi 'Fake Vendor' $tmp/o1"
check "cross-checks agree (ethtool, ip permaddr)" "grep -q 'ethtool=agree ip-permaddr=agree' $tmp/o1"
check "no address in any spelling in the output" "noaddr $tmp/o1"
check "reference hash itself never printed" "! grep -q '0123456789abcdef' $tmp/o1"
check "ath12k dmesg: counts and hash only" "grep -q 'mac_lines=2' $tmp/o1 && grep -q 'first_addr_sha256_16=$(h16 "$HW")' $tmp/o1"

# 2. private, none: current is the firmware address, type 0; DIFFERENT reference
r=$tmp/r2; mkroot "$r" "$HW" "$HW" 0 "root=live sp11.identity=none"
echo private >"$r/usr/share/sp11/image-mode"
printf 'wifi=%s\nbt=%s\n' "$(h16 "$INJ")" "0123456789abcdef" >"$r/usr/share/sp11/identity-ref.sha256"; chmod 600 "$r/usr/share/sp11/identity-ref.sha256"
echo none >"$r/run/sp11/identity-wifi-mode"
FAKE_IW_ADDR=$HW run "$r" >"$tmp/o2"
check "private/none: switch=none, unit logged mode none" "grep -q 'identity_switch=none' $tmp/o2 && grep -q 'unit_logged_mode=none' $tmp/o2"
check "private/none: permanent NO MATCH when reference is another address" "grep -q 'ref_match.permanent=NO MATCH' $tmp/o2"
check "private/none: current equals permanent, type 0 permanent" "grep -q 'current_equals_permanent=yes' $tmp/o2 && grep -q 'addr_assign_type=0(permanent)' $tmp/o2"
check "private/none: no address in output" "noaddr $tmp/o2"

# 3. reference with wrong mode is refused
r=$tmp/r3; mkroot "$r" "$HW" "$HW" 0 "sp11.identity=none"
echo private >"$r/usr/share/sp11/image-mode"
printf 'wifi=%s\n' "$(h16 "$HW")" >"$r/usr/share/sp11/identity-ref.sha256"; chmod 644 "$r/usr/share/sp11/identity-ref.sha256"
run "$r" >"$tmp/o3"
check "reference 0644 is refused, no comparison" "grep -q 'comparison skipped' $tmp/o3 && ! grep -q ref_match $tmp/o3"

# 4. public mode never touches the reference file: tool wrappers log every argument list
mkdir -p "$tmp/spy"
for t in stat sed cat head grep sha256sum tr awk; do
	printf '#!/bin/sh\necho "%s $*" >>"$SPY_LOG"\nexec /usr/bin/%s "$@"\n' "$t" "$t" >"$tmp/spy/$t"
	chmod +x "$tmp/spy/$t"
done
r=$tmp/r4; mkroot "$r" "$HW" "$INJ" 3 "sp11.entry=debug"
printf 'wifi=%s\n' "$(h16 "$HW")" >"$r/usr/share/sp11/identity-ref.sha256"; chmod 600 "$r/usr/share/sp11/identity-ref.sha256"
export SPY_LOG=$tmp/spy.log; : >"$SPY_LOG"
PATH="$tmp/spy:$tmp/bin:$PATH" SP11_ID_ROOT=$r SP11_ID_ALLOW_NONROOT=1 timeout 20 bash -c ". '$here/collector/identity.sh'" >"$tmp/o4" 2>&1
check "public: no tool was given the reference path" "! grep -q 'identity-ref' $SPY_LOG && [ -s $SPY_LOG ]"
check "public: reference not read, no ref_match line" "grep -q 'reference: not read (public mode)' $tmp/o4 && ! grep -q ref_match $tmp/o4"
check "public: no address in output" "noaddr $tmp/o4"
echo private >"$r/usr/share/sp11/image-mode"; : >"$SPY_LOG"
PATH="$tmp/spy:$tmp/bin:$PATH" SP11_ID_ROOT=$r SP11_ID_ALLOW_NONROOT=1 timeout 20 bash -c ". '$here/collector/identity.sh'" >"$tmp/o4b" 2>&1
check "control: private mode does read it (the spy is sensitive)" "grep -q 'identity-ref' $SPY_LOG && grep -q 'ref_match.permanent=MATCH' $tmp/o4b"

# 5. locally administered permanent address: class not applicable; assignment bits only
r=$tmp/r5; mkroot "$r" "$INJ" "$INJ" 1 "x"
run "$r" >"$tmp/o5"
check "locally administered scope detected, oui_class not-applicable" "grep -q 'scope=locally-administered' $tmp/o5 && grep -q 'oui_class=not-applicable' $tmp/o5"
check "random assign type named" "grep -q 'addr_assign_type=1(random)' $tmp/o5"
check "no address in output (LA case)" "noaddr $tmp/o5"

# 6. no phy
r=$tmp/r6; mkdir -p "$r/proc"; echo "root=x" >"$r/proc/cmdline"
run "$r" >"$tmp/o6"
check "no phy: explicit message" "grep -q 'no ieee80211 netdev present' $tmp/o6"

# 7. a tool that leaks an address is masked by the final filter
cat >"$tmp/bin/dmesg" <<EOT
#!/bin/sh
echo "ath12k leak $HW and ${HW^^}"
EOT
r=$tmp/r7; mkroot "$r" "$HW" "$HW" 0 "x"
run "$r" >"$tmp/o7"
check "final mask: no address even if a tool prints one" "noaddr $tmp/o7"

# 8. gate script
g=$here/userspace/sp11-wifi-identity
for c in "sp11.identity=none:none" "x:inject" "sp11.identity=inject:inject" "sp11.identity=bogus:inject"; do
	r=$tmp/g; rm -rf "$r"; mkdir -p "$r/proc" "$r/etc/NetworkManager/conf.d"; echo "root=x ${c%%:*}" >"$r/proc/cmdline"
	echo "# $INJ" >"$r/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf"
	SP11_ID_ROOT=$r SP11_ID_DRY_RUN=1 "$g" >"$tmp/go" 2>&1
	check "gate '${c%%:*}' uses mode ${c##*:}, logs it" "[ \"\$(cat $r/run/sp11/identity-wifi-mode)\" = ${c##*:} ] && grep -q 'mode=${c##*:}' $tmp/go"
	check "gate '${c%%:*}': address not logged, file untouched" "noaddr $tmp/go && grep -qF '$INJ' $r/etc/NetworkManager/conf.d/90-sp11-wifi-mac.conf"
done

# 9. shellcheck (skipped with a notice when absent)
if command -v shellcheck >/dev/null 2>&1; then
	check "shellcheck collector/identity.sh" "shellcheck -s bash -e SC2034 '$here/collector/identity.sh'"
	check "shellcheck userspace/sp11-wifi-identity" "shellcheck '$here/userspace/sp11-wifi-identity'"
	check "shellcheck tests/identity-test.sh" "shellcheck -x -e SC2016,SC2086 '$here/tests/identity-test.sh'"
else
	echo "skip shellcheck (not installed)"
fi

echo "failures: $fails"
[ "$fails" -eq 0 ]
