# SP11 log collector drop-in, OPTIONAL and NOT read-only: install as
# /etc/sp11-log-collector.d/wifi-unblock-probe.sh only in the ISO that tests the rfkill finding
# (hardware/wifi/README.md, Q4). Owner: wifi worker; installed by the image worker.
#
# What it changes: the rfkill SOFT-block state of the Wi-Fi radio (a userspace flag in the
# kernel's rfkill core, lost at reboot) and the NetworkManager radio switch. Nothing is written to
# the device, to firmware, to the disk or to the ESP (S3, S4 unaffected). Runs once per boot, 90 s
# after boot, so the first snapshots show the untouched state.
# Output goes to extra-wifi-unblock-probe.txt; masks MAC-shaped strings.

mask() { sed -E 's/([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}/<MAC>/g'; }
[ -e /run/sp11-wifi-unblock.done ] && { echo "already done in this boot"; return 0 2>/dev/null || true; }
[ "$(cut -d. -f1 /proc/uptime)" -ge 90 ] || { echo "skipped: uptime < 90 s"; return 0 2>/dev/null || true; }
touch /run/sp11-wifi-unblock.done

echo "== before"
rfkill --output ID,TYPE,DEVICE,SOFT,HARD 2>&1 | mask
nmcli -t -f DEVICE,TYPE,STATE dev 2>&1 | mask
nmcli radio 2>&1

echo "== rfkill unblock wifi, nmcli radio wifi on"
rfkill unblock wifi 2>&1
timeout 10 nmcli radio wifi on 2>&1
sleep 8

echo "== after (8 s later)"
rfkill --output ID,TYPE,DEVICE,SOFT,HARD 2>&1 | mask
nmcli -t -f DEVICE,TYPE,STATE dev 2>&1 | mask
nmcli radio 2>&1
for i in $(ls /sys/class/ieee80211/*/device/net 2>/dev/null); do
	echo "### scan $i (counts only)"
	timeout 25 iw dev "$i" scan 2>&1 | awk '/^BSS /{n++} /^\tfreq:/{f=int($2); if (f<3000) a++; else if (f<5900) b++; else c++} /command failed|Network is down|busy/{print "iw error: " $0} END{printf "bss_total=%d 2g4=%d 5g=%d 6g=%d\n", n, a, b, c}'
done
echo "== kernel log tail (ath12k, rfkill)"
dmesg | grep -i -E 'ath12k|rfkill' | tail -20 | mask
