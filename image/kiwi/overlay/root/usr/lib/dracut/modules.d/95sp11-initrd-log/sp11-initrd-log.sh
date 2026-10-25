#!/bin/sh
# SP11 initramfs log capture: sp11-initrd-log REASON   (REASON: emergency | initqueue-timeout)
#
# Writes <ESP>/EFI/sp11-logs/initrd-<boot-id>/ with, per reason: journal, dmesg, rdsosreport and a
# state report, all gzip-compressed (the collector's ESP rule), and STATUS, SEQ and COMPLETE. The
# boot id is the one the collector uses in the real root, so initrd-<id> and <id> belong together.
# Cap: CAP_ESP_KIB of /etc/sp11-log-collector.conf (default 6144 KiB); the oldest other boot
# directory (by SEQ) goes first. Reads only; the only writes are to the ESP and /run.
# Runs at most once per reason. Never fails the boot: every error is swallowed.
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin
reason=${1:-unknown}
[ -e "/run/sp11-initrd-log.$reason" ] && exit 0
: >"/run/sp11-initrd-log.$reason"

LOGS_LABEL=SP11LOGS ESP_LABEL=BOOT CAP_ESP_KIB=6144 RESERVE_KIB=512
[ -r /etc/sp11-log-collector.conf ] && . /etc/sp11-log-collector.conf
MNT=/run/sp11-esp
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown-boot)
say() { echo "sp11-initrd-log: $*" >&2; }

mkdir -p "$MNT"
modprobe vfat 2>/dev/null
dev=
for cand in $(blkid -t "LABEL=$ESP_LABEL" -o device 2>/dev/null); do
	if mount -t vfat -o rw,noatime,nodev,nosuid,noexec,umask=0077,shortname=winnt "$cand" "$MNT" 2>/dev/null; then
		dev=$cand
		break
	fi
done
if [ -z "$dev" ]; then
	say "no writable FAT partition labelled $ESP_LABEL ($reason); nothing written"
	exit 0
fi

root=$MNT/EFI/sp11-logs
bd=$root/initrd-$BOOT_ID
mkdir -p "$bd" || { umount "$MNT"; exit 0; }
if [ ! -e "$bd/SEQ" ]; then
	seq=$(($(cat "$root/.seq" 2>/dev/null || echo 0) + 1))
	echo "$seq" >"$root/.seq"
	echo "$seq" >"$bd/SEQ"
fi

gz() { gzip -c -6 >"$bd/$1.gz"; }   # gz NAME < data
{
	echo "reason: $reason"
	echo "boot_id: $BOOT_ID"
	echo "date_utc: $(date -u +%FT%TZ)"
	echo "uptime: $(cut -d' ' -f1 /proc/uptime)"
	echo "esp_device: $dev"
} >"$bd/STATUS.$reason"
journalctl -b --no-pager -o short-monotonic 2>&1 | gz "journal-$reason.txt"
dmesg --time-format=iso 2>&1 | gz "dmesg-$reason.txt"
# dracut's own report (the emergency path has made it already; the timeout path has not)
[ -s /run/initramfs/rdsosreport.txt ] || /sbin/rdsosreport >/dev/null 2>&1
{ cat /run/initramfs/rdsosreport.txt 2>&1; } | gz "rdsosreport-$reason.txt"
{
	echo "== /proc/cmdline"; cat /proc/cmdline
	echo "== blkid"; blkid 2>&1
	echo "== lsblk"; lsblk -o NAME,KNAME,FSTYPE,LABEL,SIZE,RM,MOUNTPOINT 2>&1
	echo "== /dev/disk/by-label"; ls -l /dev/disk/by-label 2>&1
	echo "== initqueue finished hooks"; for f in /lib/dracut/hooks/initqueue/finished/*.sh; do [ -e "$f" ] && { echo "$f: $(cat "$f")"; }; done
	echo "== /proc/modules (first 200)"; head -n 200 /proc/modules
	echo "== devices_deferred"; cat /sys/kernel/debug/devices_deferred 2>&1
} 2>&1 | gz "state-$reason.txt"

# cap: oldest other boot directories first (by SEQ; the clock may be wrong), never the current one
used() { du -sk "$root" 2>/dev/null | cut -f1; }
cap=$CAP_ESP_KIB
free=$(df -Pk "$MNT" 2>/dev/null | awk 'NR==2{print $4}')
cur=$(du -sk "$bd" 2>/dev/null | cut -f1)
[ -n "$free" ] && [ $((cur + free - RESERVE_KIB)) -lt "$cap" ] && cap=$((cur + free - RESERVE_KIB))
while [ "$(used)" -gt "$cap" ]; do
	old=$(for d in $(find "$root" -mindepth 1 -maxdepth 1 -type d ! -name "initrd-$BOOT_ID"); do echo "$(cat "$d/SEQ" 2>/dev/null || echo 0) $d"; done | sort -n | head -n1 | cut -d' ' -f2-)
	[ -n "$old" ] || break
	rm -rf "$old"
	sync
done
date -u +%FT%TZ >"$bd/COMPLETE"
sync
umount "$MNT" 2>/dev/null
say "wrote $reason capture to $dev:/EFI/sp11-logs/initrd-$BOOT_ID"
exit 0
