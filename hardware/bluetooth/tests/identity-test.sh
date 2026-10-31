#!/usr/bin/bash
# Fixture tests for the Bluetooth identity experiment (collector/sp11-identity-bt) and the
# sp11.identity switch of userspace/sp11-bt-address (that part is in userspace/check.py).
# Fake sysfs and a fake btmgmt; the addresses are synthetic and exist only in this test.
# Run: hardware/bluetooth/tests/identity-test.sh
set -uo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
fails=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

HW=a4:bb:cc:dd:ee:01 # what a fake controller with a valid OTP address reports
INJ=02:11:22:33:44:66 # what the injection would set
h16() { printf '%s' "$1" | tr 'A-F' 'a-f' | sha256sum | cut -c1-16; }
ADDRS=("$HW" "${HW^^}" "${HW//:/}" "${HW^^//:/}" "${HW//:/_}" "$INJ" "${INJ^^}" "${INJ//:/}" "${INJ^^//:/}")
noaddr() { local a; for a in "${ADDRS[@]}"; do grep -qiF -- "$a" "$1" && return 1; done; return 0; }
noaddr_tree() { local f; while IFS= read -r f; do noaddr "$f" || return 1; done < <(find "$1" -type f); }

mkroot() { # $1 dir, $2 cmdline, $3 compatible ('' = no hci0)
	local r=$1
	mkdir -p "$r/proc" "$r/usr/share/sp11" "$r/run"
	printf '%s\n' "$2" >"$r/proc/cmdline"
	echo "50.0 40.0" >"$r/proc/uptime"
	if [ -n "$3" ]; then
		mkdir -p "$r/sys/class/bluetooth/hci0/device/of_node"
		printf '%s\0' "$3" >"$r/sys/class/bluetooth/hci0/device/of_node/compatible"
	fi
}
mkbin() {
	mkdir -p "$tmp/bin"
	cat >"$tmp/bin/btmgmt" <<'EOT'
#!/bin/sh
# state file: "unconfigured" | "configured <addr>" | "sentinel"
st=$(cat "$BT_FAKE_STATE")
op=""; for a in "$@"; do case "$a" in config|info) op=$a ;; esac; done
case "$st" in
unconfigured)
	if [ "$op" = config ]; then printf 'hci0: Unconfigured controller\n\tsupported options: public-address \n\tmissing options: public-address \n'
	else echo "Reading hci0 info failed with status 0x12 (Not Configured)"; fi ;;
sentinel)
	if [ "$op" = config ]; then printf 'hci0: Unconfigured controller\n\tsupported options: public-address \n\tmissing options: public-address \n'
	else printf 'hci0: Primary controller\n\taddr 00:00:00:00:5A:AD version 13 manufacturer 29 class 0x000000\n'; fi ;;
configured*)
	if [ "$op" = config ]; then printf 'hci0: Configured controller\n\tsupported options: public-address \n\tmissing options: \n'
	else printf 'hci0: Primary controller\n\taddr %s version 13 manufacturer 29 class 0x000000\n' "${st#configured }"; fi ;;
esac
EOT
	chmod +x "$tmp/bin/btmgmt"
}
mkbin
run() { # $1 root, $2 pre|report
	PATH="$tmp/bin:$PATH" SP11_ID_ROOT=$1 SP11_ID_SLEEP=0 SP11_ID_ALLOW_NONROOT=1 BT_FAKE_STATE="$tmp/state" timeout 60 "$here/collector/sp11-identity-bt" "$2" 2>&1
}
privref() { # $1 root, $2 bt hash
	echo private >"$1/usr/share/sp11/image-mode"
	printf 'wifi=0123456789abcdef\nbt=%s\n' "$2" >"$1/usr/share/sp11/identity-ref.sha256"
	chmod 600 "$1/usr/share/sp11/identity-ref.sha256"
}

# 1. controller has its own valid address (OTP): configured, MATCH against the reference
r=$tmp/r1; mkroot "$r" "root=x sp11.identity=none" qcom,wcn7850-bt; privref "$r" "$(h16 "$HW")"
echo "configured $HW" >"$tmp/state"
run "$r" pre >"$tmp/p1"; run "$r" report >"$tmp/o1"
check "configured: state configured, address hash present, MATCH" "grep -q 'bt.state=configured' $tmp/o1 && grep -q 'bt.addr.sha256_16=$(h16 "$HW") scope=universal' $tmp/o1 && grep -q 'bt.ref_match=MATCH' $tmp/o1"
check "configured: interpretation says the controller supplies it" "grep -q 'presents a configured public address itself' $tmp/o1"
check "configured: switch none shown in both snapshots" "[ \$(grep -c 'identity_switch=none' $tmp/o1) -eq 2 ]"
check "no address anywhere (output, pre file)" "noaddr $tmp/o1 && noaddr_tree $r/run"
check "state dir 0700, pre file 0600" "[ \$(stat -c %a $r/run/sp11-identity) = 700 ] && [ \$(stat -c %a $r/run/sp11-identity/bt-pre.txt) = 600 ]"
check "reference hash and constants not printed" "! grep -q 0123456789abcdef $tmp/o1"

# 2. unconfigured controller (M8 behaviour): no address readable, injection needed
r=$tmp/r2; mkroot "$r" "root=x sp11.identity=none" qcom,wcn7850-bt; privref "$r" "$(h16 "$HW")"
echo unconfigured >"$tmp/state"
run "$r" report >"$tmp/o2"
check "unconfigured: missing public-address recorded" "grep -q 'bt.state=unconfigured missing_options=\[public-address\]' $tmp/o2"
check "unconfigured: info refused, address not readable, NO MATCH" "grep -q 'Not Configured' $tmp/o2 && grep -q 'bt.addr=not-readable' $tmp/o2 && grep -q 'NO MATCH' $tmp/o2"
check "unconfigured: interpretation says supply an address" "grep -q 'an address must be supplied' $tmp/o2"

# 3. default NVM sentinel presented as the address
r=$tmp/r3; mkroot "$r" "x" qcom,wcn7850-bt; privref "$r" "$(h16 "$HW")"
echo sentinel >"$tmp/state"
run "$r" report >"$tmp/o3"
check "sentinel: default_nvm_sentinel=yes, NO MATCH" "grep -q 'default_nvm_sentinel=yes' $tmp/o3 && grep -q 'bt.ref_match=NO MATCH' $tmp/o3"

# 4. pre snapshot survives the injection: pre says unconfigured, now says configured/injected
r=$tmp/r4; mkroot "$r" "root=x" qcom,wcn7850-bt; privref "$r" "$(h16 "$INJ")"
echo unconfigured >"$tmp/state"; run "$r" pre >/dev/null
echo "configured $INJ" >"$tmp/state"; run "$r" report >"$tmp/o4"
check "pre vs now: pre unconfigured NO MATCH, now configured MATCH" "awk '/snapshot: pre/{s=\"pre\"} /snapshot: now/{s=\"now\"} s==\"pre\"&&/bt.state=unconfigured/{a=1} s==\"now\"&&/bt.state=configured/{b=1} s==\"now\"&&/ref_match=MATCH/{c=1} END{exit !(a&&b&&c)}' $tmp/o4"
check "pre vs now: no address in output" "noaddr $tmp/o4 && noaddr_tree $r/run"
r=$tmp/r4b; mkroot "$r" "root=x" qcom,wcn7850-bt
run "$r" report >"$tmp/o4b"
check "report without pre file says so" "grep -q 'pre MISSING' $tmp/o4b"

# 5. public mode never touches the reference file (tool spy logs every argument list)
mkdir -p "$tmp/spy"
for t in stat sed cat head grep sha256sum tr awk; do
	printf '#!/bin/sh\necho "%s $*" >>"$SPY_LOG"\nexec /usr/bin/%s "$@"\n' "$t" "$t" >"$tmp/spy/$t"; chmod +x "$tmp/spy/$t"
done
r=$tmp/r5; mkroot "$r" "root=x" qcom,wcn7850-bt
printf 'wifi=0123456789abcdef\nbt=%s\n' "$(h16 "$HW")" >"$r/usr/share/sp11/identity-ref.sha256"; chmod 600 "$r/usr/share/sp11/identity-ref.sha256"
echo "configured $HW" >"$tmp/state"; export SPY_LOG=$tmp/spy.log; : >"$SPY_LOG"
PATH="$tmp/spy:$tmp/bin:$PATH" SP11_ID_ROOT=$r SP11_ID_SLEEP=0 SP11_ID_ALLOW_NONROOT=1 BT_FAKE_STATE="$tmp/state" "$here/collector/sp11-identity-bt" report >"$tmp/o5" 2>&1
check "public: no tool was given the reference path" "! grep -q 'identity-ref' $SPY_LOG && [ -s $SPY_LOG ]"
check "public: no ref_match line, reference not read" "! grep -q ref_match $tmp/o5 && grep -q 'reference: not read (public mode)' $tmp/o5"
check "public: no address in output" "noaddr $tmp/o5"
echo private >"$r/usr/share/sp11/image-mode"; : >"$SPY_LOG"
PATH="$tmp/spy:$tmp/bin:$PATH" SP11_ID_ROOT=$r SP11_ID_SLEEP=0 SP11_ID_ALLOW_NONROOT=1 BT_FAKE_STATE="$tmp/state" "$here/collector/sp11-identity-bt" report >"$tmp/o5b" 2>&1
check "control: private mode does read it (the spy is sensitive)" "grep -q 'identity-ref' $SPY_LOG && grep -q 'ref_match=MATCH' $tmp/o5b"

# 6. reference with wrong mode refused; no hci0; other controller; tool that prints an address
r=$tmp/r6; mkroot "$r" "x" qcom,wcn7850-bt; privref "$r" "$(h16 "$HW")"; chmod 644 "$r/usr/share/sp11/identity-ref.sha256"
run "$r" report >"$tmp/o6"
check "reference 0644 refused" "grep -q 'comparison skipped' $tmp/o6 && ! grep -q ref_match $tmp/o6"
r=$tmp/r7; mkroot "$r" "x" ""
run "$r" report >"$tmp/o7"
check "no hci0 reported" "grep -q 'bt.controller_hci0=absent' $tmp/o7"
r=$tmp/r8; mkroot "$r" "x" some,usb-dongle
run "$r" report >"$tmp/o8"
check "other controller is flagged, not treated as WCN7850" "grep -q 'bt.controller_hci0=other-or-unknown' $tmp/o8"
printf '#!/bin/sh\nprintf "hci0:\\tType: Primary\\n\\tBD Address: %s  ACL MTU: 1021:8\\n"\n' "${HW^^}" >"$tmp/bin/hciconfig"; chmod +x "$tmp/bin/hciconfig"
r=$tmp/r9; mkroot "$r" "x" qcom,wcn7850-bt; echo unconfigured >"$tmp/state"
run "$r" report >"$tmp/o9"
check "hciconfig fallback hashes the address, never prints it" "grep -q 'bt.addr_source=hciconfig' $tmp/o9 && noaddr $tmp/o9"
rm -f "$tmp/bin/hciconfig"

# 7. shellcheck and the drop-in/units
if command -v shellcheck >/dev/null 2>&1; then
	check "shellcheck sp11-identity-bt, helper, tests" "shellcheck '$here/collector/sp11-identity-bt' '$here/userspace/sp11-bt-address' && shellcheck -e SC2016,SC2086 '$here/tests/identity-test.sh'"
else
	echo "skip shellcheck (not installed)"
fi
check "pre unit orders before the injection unit" "grep -q '^Before=sp11-bt-address.service' '$here/collector/sp11-identity-bt-pre.service'"

echo "failures: $fails"
[ "$fails" -eq 0 ]
