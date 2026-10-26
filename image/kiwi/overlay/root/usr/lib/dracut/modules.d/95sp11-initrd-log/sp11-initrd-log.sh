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

# ---- boot medium (risk S4): the same rules as the collector. Write only to a partition of the disk the
# live system is booting from, never to another disk (the test device is also a Windows machine), and
# never to a disk that carries NTFS, BitLocker or a Microsoft reserved partition.
SP11_MSR_GUID=e6d6d379-f507-44c2-a23c-238f2a3df928
pkname() {
	_n=${1##*/}
	if [ -e "/sys/class/block/$_n/partition" ]; then basename "$(readlink -f "/sys/class/block/$_n/..")"; else echo "$_n"; fi
}
BOOT_DISK= BOOT_HOW=
_label=
for _a in $(cat /proc/cmdline 2>/dev/null); do
	case $_a in root=live:CDLABEL=*) _label=${_a#root=live:CDLABEL=} ;; root=live:LABEL=*) _label=${_a#root=live:LABEL=} ;; esac
done
if [ -n "$_label" ]; then
	_dev=$(blkid -L "$_label" 2>/dev/null | head -n1)
	[ -n "$_dev" ] && { BOOT_DISK=$(pkname "$_dev"); BOOT_HOW="cmdline label $_label -> $_dev"; }
fi
if [ -z "$BOOT_DISK" ]; then
	_src=$(awk '$2=="/run/initramfs/live"{print $1}' /proc/mounts 2>/dev/null | head -n1)
	[ -n "$_src" ] && [ -b "$_src" ] && { BOOT_DISK=$(pkname "$_src"); BOOT_HOW="live mount source $_src"; }
fi
if [ -z "$BOOT_DISK" ] && [ -r /etc/sp11-boot-medium ]; then
	# the label the ISO was built with (a wrong or missing root= label is the very failure this hook is for)
	. /etc/sp11-boot-medium
	_dev=$(blkid -L "$SP11_MEDIUM_LABEL" 2>/dev/null | head -n1)
	[ -n "$_dev" ] && { BOOT_DISK=$(pkname "$_dev"); BOOT_HOW="built-in ISO label $SP11_MEDIUM_LABEL -> $_dev"; }
fi
if [ -z "$BOOT_DISK" ]; then
	say "S4: boot medium unknown ($reason: root=live:CDLABEL=$_label does not resolve, no live mount): writing nothing"
	exit 0
fi
say "boot medium: $BOOT_DISK ($BOOT_HOW)"
win=0
for _part in /sys/class/block/"$BOOT_DISK"/"$BOOT_DISK"*; do
	[ -e "$_part/partition" ] || continue
	_t=$(blkid -p -o value -s TYPE "/dev/${_part##*/}" 2>/dev/null | tr 'A-Z' 'a-z')
	_g=$(blkid -p -o value -s PART_ENTRY_TYPE "/dev/${_part##*/}" 2>/dev/null | tr 'A-Z' 'a-z')
	case $_t in ntfs | bitlocker*) win=1 ;; esac
	[ "$_g" = "$SP11_MSR_GUID" ] && win=1
done
if [ "$win" = 1 ]; then
	say "S4: disk $BOOT_DISK carries NTFS, BitLocker or a Microsoft reserved partition: refusing to write to it"
	exit 0
fi

mkdir -p "$MNT"
modprobe vfat 2>/dev/null
dev=
for cand in $(blkid -t "LABEL=$ESP_LABEL" -o device 2>/dev/null); do
	[ "$(pkname "$cand")" = "$BOOT_DISK" ] || continue
	if mount -t vfat -o rw,noatime,nodev,nosuid,noexec,umask=0077,shortname=winnt "$cand" "$MNT" 2>/dev/null; then
		dev=$cand
		break
	fi
done
if [ -z "$dev" ]; then
	say "no writable FAT partition labelled $ESP_LABEL on the boot medium $BOOT_DISK ($reason); nothing written"
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
	echo "boot_medium: $BOOT_DISK ($BOOT_HOW)"
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
for _i in 1 2 3 4 5; do
	grep -q " $MNT " /proc/mounts 2>/dev/null || break
	umount "$MNT" 2>/dev/null || sleep 1
done
grep -q " $MNT " /proc/mounts 2>/dev/null && say "WARNING: $MNT still mounted after 5 umount attempts"
sync
say "wrote $reason capture to $dev:/EFI/sp11-logs/initrd-$BOOT_ID"
exit 0
