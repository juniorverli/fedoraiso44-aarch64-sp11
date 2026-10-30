#!/usr/bin/bash
# SP11 GPU two-step diagnostic collector (gpu worker; for the image owner to install as
# /usr/libexec/sp11-gpu-two-step, run by sp11-gpu-two-step.service).
#
# Purpose: find which step of GPU bring-up resets the machine silently, and keep the evidence
# on the boot medium although the reset gives no warning. Runs ONLY when the kernel command line
# has sp11.gpu_diag=1 (the GRUB entry "SP11 debug, GPU diagnostic"). On any other boot it exits 0.
#
#   Step 0  baseline snapshot, firmware presence, kernel log follower started (fsync per record)
#   Step 1  runtime-PM "on" for the GMU device (3d6a000.gmu: powers the CX GDSC and nothing else
#           by itself) and for the GPU device (3d00000.gpu; a no-op until the first render open,
#           recorded to prove it), then 20 s of sampling
#   Step 2  ONE open() of the msm render node. msm_open() calls load_gpu() (msm_drv.c:271) which
#           runs adreno_load_gpu(): firmware load, runtime-PM enable, GMU boot (a6xx_gmu_resume),
#           then hw_init with the zap shader (PAS 13). These happen inside that single call, so
#           the step cannot be split from userspace; kernel markers are requested separately.
#           Then 20 s of sampling and close.
#
# Survival: before and after every step the script appends a marker to state.log on the boot
# medium, then runs `sync -f` on that file system. The next diagnostic boot reads state.log and
# says "previous boot died during step N" (previous-boot-report.txt, kmsg, journal).
# After a death in step N, every later boot of the same kernel release runs only the steps below N
# unless sp11.gpu_diag_force=1, so a reset loop cannot form.
#
# Risk S4: writes only to a FAT partition (label SP11LOGS, else ANACONDA) of the disk the live
# system booted from; never to any other disk; refuses a disk that carries NTFS, BitLocker or a
# Microsoft reserved partition. Same method as /usr/libexec/sp11-log-collector (find_boot_disk,
# disk_has_windows, on_boot_disk); copied in short form because that script cannot be sourced
# without running. Image owner: replace the copy by a sourced library if you factor it out.
# The script reads sysfs and the debugfs files on the collector's allow-list only (never dri/*/state).
set -u
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin

# Test hooks (image/tools self-test): SP11_GPU_* override paths; defaults are the real system.
CMDLINE_FILE=${SP11_GPU_CMDLINE:-/proc/cmdline}
SYS=${SP11_GPU_SYS:-/sys}
DBG=${SP11_GPU_DEBUGFS:-/sys/kernel/debug}
FWDIR=${SP11_GPU_FW:-/usr/lib/firmware}
GPU_DEV=${SP11_GPU_DEV:-3d00000.gpu}
GMU_DEV=${SP11_GPU_GMU:-3d6a000.gmu}
WAIT_S=${SP11_GPU_WAIT:-20}            # seconds of sampling after each step
SAMPLE_S=${SP11_GPU_SAMPLE:-5}
BIND_TIMEOUT=${SP11_GPU_BIND_TIMEOUT:-90}
BOOT_ID=${SP11_TEST_BOOT_ID:-$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || echo unknown-boot)}
MNT=/run/sp11-gpu-mnt
RUN=${SP11_GPU_RUN:-/run/sp11-gpu-two-step}
ROOT= STATE= OUT= KMSG_PID=

say() { echo "sp11-gpu-two-step: $*" >&2; echo "sp11-gpu-two-step: $*" 2>/dev/null >/dev/kmsg; }
upt() { cut -d' ' -f1 /proc/uptime 2>/dev/null; }

# ------------------------------------------------------------ gate -------
cmdline_has() { tr ' ' '\n' <"$CMDLINE_FILE" | grep -qx -- "$1"; }
cmdline_has sp11.gpu_diag=1 || exit 0

# ------------------------------------------------- boot medium (S4) -------
SP11_MSR_GUID=e6d6d379-f507-44c2-a23c-238f2a3df928
pkname() { local n=${1##*/}; if [ -e "$SYS/class/block/$n/partition" ]; then basename "$(readlink -f "$SYS/class/block/$n/..")"; else echo "$n"; fi; }
find_boot_disk() {
	local a label= dev src
	for a in $(cat "$CMDLINE_FILE"); do
		case $a in root=live:CDLABEL=*) label=${a#root=live:CDLABEL=} ;; root=live:LABEL=*) label=${a#root=live:LABEL=} ;; esac
	done
	if [ -n "$label" ]; then dev=$(blkid -L "$label" 2>/dev/null | head -n1); [ -n "$dev" ] && { pkname "$dev"; return 0; }; fi
	src=$(awk '$2=="/run/initramfs/live"{print $1}' /proc/mounts 2>/dev/null | head -n1)
	[ -n "$src" ] && [ -b "$src" ] && { pkname "$src"; return 0; }
	if [ -r /etc/sp11-boot-medium ]; then
		. /etc/sp11-boot-medium
		dev=$(blkid -L "$SP11_MEDIUM_LABEL" 2>/dev/null | head -n1); [ -n "$dev" ] && { pkname "$dev"; return 0; }
	fi
	return 1
}
disk_has_windows() {
	local part t g
	for part in "$SYS/class/block/$1/$1"*; do
		[ -e "$part/partition" ] || continue
		t=$(blkid -p -o value -s TYPE "/dev/${part##*/}" 2>/dev/null | tr 'A-Z' 'a-z')
		g=$(blkid -p -o value -s PART_ENTRY_TYPE "/dev/${part##*/}" 2>/dev/null | tr 'A-Z' 'a-z')
		case $t in ntfs | bitlocker*) return 0 ;; esac
		[ "$g" = "$SP11_MSR_GUID" ] && return 0
	done
	return 1
}
find_root() { # sets ROOT (directory for state.log and boot dirs); returns 1 when no safe medium
	local disk dev cand
	if [ -n "${SP11_GPU_TARGET:-}" ]; then ROOT=$SP11_GPU_TARGET; mkdir -p "$ROOT"; return 0; fi
	disk=$(find_boot_disk) || { say "S4: boot medium unknown; writing nothing outside /run"; return 1; }
	if disk_has_windows "$disk"; then say "S4: disk $disk carries NTFS/BitLocker/MSR; refusing"; return 1; fi
	for lbl in SP11LOGS ANACONDA; do
		dev=
		for cand in $(blkid -t "LABEL=$lbl" -o device 2>/dev/null); do [ "$(pkname "$cand")" = "$disk" ] && { dev=$cand; break; }; done
		[ -n "$dev" ] || continue
		mkdir -p "$MNT"; modprobe vfat 2>/dev/null
		findmnt -n "$MNT" >/dev/null 2>&1 || mount -t vfat -o rw,noatime,nodev,nosuid,noexec,umask=0077,shortname=winnt "$dev" "$MNT" 2>/dev/null || continue
		if [ "$lbl" = SP11LOGS ]; then ROOT=$MNT/gpu-two-step; else ROOT=$MNT/EFI/sp11-logs/gpu-two-step; fi
		mkdir -p "$ROOT" && touch "$ROOT/.w" 2>/dev/null && { rm -f "$ROOT/.w"; return 0; }
		umount "$MNT" 2>/dev/null
	done
	say "S4: no writable SP11LOGS/ANACONDA FAT partition on boot disk $disk"
	return 1
}

# ---------------------------------------------------------- markers -------
flush() { sync -f "$STATE" 2>/dev/null || sync; }
mark() { # mark EVENT: append to state.log, flush to the medium, echo to kmsg
	printf 'T=%s UP=%s BOOT=%s EVENT=%s\n' "$(date +%s)" "$(upt)" "$BOOT_ID" "$*" >>"$STATE"
	flush
	echo "sp11-gpu-two-step: $*" 2>/dev/null >/dev/kmsg
	return 0
}
# stamp NAME CMD...: output of CMD into $OUT/NAME, flushed
snap() { local n=$1; shift; timeout 30 "$@" >"$OUT/$n" 2>&1; }
dbgcat() { # allow-list only (same files as sp11-log-collector debugfs_allowed)
	case $1 in */clk/clk_summary|*/pm_genpd/pm_genpd_summary|*/regulator/regulator_summary|*/devfreq/devfreq_summary|*/devices_deferred) timeout 5 cat "$1" 2>&1 ;; *) echo "# not read: $1" ;; esac
}
attrs() { local d f; for d in "$@"; do [ -d "$d" ] || { echo "# absent $d"; continue; }; echo "== $d"; for f in "$d"/*; do [ -f "$f" ] && [ -r "$f" ] && printf '%s: %s\n' "${f##*/}" "$(timeout 2 head -c 200 "$f" 2>&1 | tr '\n' ' ')"; done; done; }
capture() { # capture TAG: the state asked for in the task, one file per item, flushed
	local t=$1
	snap "$t.dmesg" dmesg
	dbgcat "$DBG/regulator/regulator_summary" >"$OUT/$t.regulators" 2>&1
	dbgcat "$DBG/clk/clk_summary" >"$OUT/$t.clocks" 2>&1
	dbgcat "$DBG/pm_genpd/pm_genpd_summary" >"$OUT/$t.genpd" 2>&1
	{ attrs "$SYS/bus/platform/devices/$GPU_DEV/power" "$SYS/bus/platform/devices/$GMU_DEV/power" "$SYS/class/devfreq/$GPU_DEV"
	  echo "driver gpu: $(readlink "$SYS/bus/platform/devices/$GPU_DEV/driver" 2>&1)"
	  echo "driver gmu: $(readlink "$SYS/bus/platform/devices/$GMU_DEV/driver" 2>&1)"; } >"$OUT/$t.pm" 2>&1
	flush
}

# ------------------------------------------------- kernel log follower ----
# Every kernel record is appended and fsynced at once, so the last lines before a reset survive
# (printk.devkmsg=on and log_buf_len=16M are on the command line of this entry).
start_follower() {
	( stdbuf -oL dmesg -w 2>&1 | while IFS= read -r l; do printf '%s\n' "$l" >>"$OUT/kmsg-follow.txt"; sync "$OUT/kmsg-follow.txt" 2>/dev/null; done ) &
	KMSG_PID=$!
}

# ---------------------------------------------- previous-boot report ------
# last_events: one line per earlier boot (not the current one): "<boot-id> <uptime> <epoch> <last event>"
last_events() {
	awk -v cur="$BOOT_ID" '{
		b = $0; sub(/^.*BOOT=/, "", b); sub(/ .*$/, "", b)
		u = $0; sub(/^.*UP=/, "", u); sub(/ .*$/, "", u)
		t = $0; sub(/^T=/, "", t); sub(/ .*$/, "", t)
		e = $0; sub(/^.*EVENT=/, "", e)
		if (b == cur) next
		if (!(b in seen)) { seen[b] = 1; order[++n] = b }
		ev[b] = e; up[b] = u; ep[b] = t }
		END { for (k = 1; k <= n; k++) { b = order[k]; print b, up[b], ep[b], ev[b] } }' "$STATE"
}
report_previous() { # writes $OUT/previous-boot-report.txt from state.log
	local rep=$OUT/previous-boot-report.txt b u t e s
	: >"$rep"
	[ -s "$STATE" ] && while read -r b u t e; do
		s=${e%%_*}; s=${s#STEP}
		case $e in
		DONE* | ABORT*) echo "boot $b: ended normally ($e)" ;;
		STEP[0-9]_END*) echo "boot $b: previous boot died AFTER step $s finished and before the next marker (uptime $u s, epoch $t)" ;;
		STEP[0-9]*) echo "boot $b: previous boot died during step $s (last marker: $e; uptime $u s, epoch $t)" ;;
		*) echo "boot $b: previous boot died before step 1 (last marker: $e; uptime $u s, epoch $t)" ;;
		esac
	done < <(last_events) >>"$rep"
	[ -s "$rep" ] || echo "no earlier diagnostic boot recorded" >"$rep"
	while IFS= read -r l; do say "REPORT $l"; done <"$rep"
}
dead_step() { # prints the lowest N (1 or 2) in which ANY earlier boot of this same kernel died, else nothing
	[ -s "$STATE" ] || return 0
	awk -v cur="$BOOT_ID" -v kv="$(uname -r)" '{
		b = $0; sub(/^.*BOOT=/, "", b); sub(/ .*$/, "", b)
		e = $0; sub(/^.*EVENT=/, "", e)
		if (b == cur) next
		if (e ~ /^BOOT_START/) { k[b] = e; sub(/^.*kver=/, "", k[b]) }
		last[b] = e }
		END { m = 0
		  for (b in last) if (k[b] == kv && last[b] ~ /^STEP[1-9]_(BEGIN|SUB|SAMPLE)/) {
		    n = last[b]; sub(/^STEP/, "", n); sub(/_.*$/, "", n); if (m == 0 || n + 0 < m) m = n + 0 }
		  if (m) print m }' "$STATE"
}

# -------------------------------------------------------------- steps -----
wait_sample() { # wait_sample TAG SECONDS: sample genpd/regulators/runtime status, one marker per sample
	local tag=$1 s=$2 t=0
	while [ "$t" -lt "$s" ]; do
		sleep "$SAMPLE_S"; t=$((t + SAMPLE_S))
		{ echo "t+$t up=$(upt)"; cat "$SYS/bus/platform/devices/$GPU_DEV/power/runtime_status" "$SYS/bus/platform/devices/$GMU_DEV/power/runtime_status" 2>&1; } >>"$OUT/$tag.samples"
		mark "${tag^^}_SAMPLE t+$t"
	done
}
find_msm_node() { # first render node whose parent device is driven by msm
	local n d
	for n in "$SYS"/class/drm/renderD*; do
		[ -e "$n" ] || continue
		d=$(readlink -f "$n/device/driver" 2>/dev/null)
		case ${d##*/} in msm*) echo "/dev/dri/${n##*/}"; return 0 ;; esac
	done
	return 1
}

step0() {
	mark STEP0_BEGIN
	local t=0
	while [ ! -e "$SYS/bus/platform/devices/$GPU_DEV/driver" ] && [ "$t" -lt "$BIND_TIMEOUT" ]; do sleep 2; t=$((t + 2)); done
	if [ ! -e "$SYS/bus/platform/devices/$GPU_DEV/driver" ]; then mark "ABORT $GPU_DEV not bound after ${BIND_TIMEOUT}s (DTB without GPU?)"; return 1; fi
	local f miss=0
	: >"$OUT/firmware.txt"
	for f in qcom/gen70500_sqe.fw qcom/gen70500_gmu.bin qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn; do
		[ -e "$FWDIR/$f" ] || [ -e "$FWDIR/$f.xz" ] || [ -e "$FWDIR/$f.zst" ] || miss=1
		ls -l "$FWDIR/$f" "$FWDIR/$f.xz" "$FWDIR/$f.zst" >>"$OUT/firmware.txt" 2>/dev/null
	done
	if [ "$miss" = 1 ]; then mark "ABORT firmware not all present (see firmware.txt)"; return 1; fi
	mountpoint -q "$DBG" 2>/dev/null || mount -t debugfs none "$DBG" 2>/dev/null
	snap lsmod lsmod; snap cmdline cat "$CMDLINE_FILE"; snap uname uname -a
	capture step0
	mark STEP0_END
}

step1() {
	mark STEP1_BEGIN
	capture step1.before
	mark STEP1_SUB write-on-gpu   # expected no-op: runtime PM of the GPU device is enabled only in adreno_load_gpu()
	echo on >"$SYS/bus/platform/devices/$GPU_DEV/power/control" 2>>"$OUT/step1.errors"
	capture step1.after-gpu-on
	mark STEP1_SUB write-on-gmu   # resumes the GMU device: CX GDSC through genpd
	echo on >"$SYS/bus/platform/devices/$GMU_DEV/power/control" 2>>"$OUT/step1.errors"
	wait_sample step1 "$WAIT_S"
	capture step1.after
	mark STEP1_END
}

step2() {
	mark STEP2_BEGIN
	local node
	node=$(find_msm_node) || { mark "ABORT no msm render node"; return 1; }
	echo "$node" >"$OUT/step2.node"
	capture step2.before
	mark "STEP2_SUB open-call $node"      # last marker before the single open(); a reset now means load_gpu() killed the machine
	exec 9<>"$node"                       # msm_open -> load_gpu -> fw, GMU boot, zap shader load (PAS 13), hw_init
	local rc=$?
	mark "STEP2_SUB open-returned rc=$rc"
	capture step2.after-open
	wait_sample step2 "$WAIT_S"
	exec 9>&-
	mark STEP2_SUB closed
	capture step2.after
	mark STEP2_END
}

# --------------------------------------------------------------- main -----
find_root || { echo "sp11-gpu-two-step: no safe target; doing nothing (S4)" >&2; exit 0; }
STATE=$ROOT/state.log
OUT=$ROOT/$BOOT_ID
mkdir -p "$OUT" "$RUN" 2>/dev/null
N=$(($(grep -c 'EVENT=BOOT_START' "$STATE" 2>/dev/null) + 1))
mark "BOOT_START n=$N kver=$(uname -r)"
echo "diagnostic boot $N" >"$OUT/boot-number"
report_previous
cp "$OUT/previous-boot-report.txt" "$RUN/report.txt" 2>/dev/null
# pstore: records of the previous boot (only present when the firmware kept RAM or EFI vars; see the evidence file)
if ls "$SYS/fs/pstore"/* >/dev/null 2>&1; then mkdir -p "$OUT/pstore" && cp -a "$SYS/fs/pstore"/. "$OUT/pstore/" 2>/dev/null; mark "PSTORE_COPIED $(ls "$SYS/fs/pstore" | wc -l) records"; fi
dead=$(dead_step)
limit=9
if [ -n "$dead" ] && ! cmdline_has sp11.gpu_diag_force=1; then limit=$((dead - 1)); say "previous boot died during step $dead: running only steps below $dead (add sp11.gpu_diag_force=1 to retry)"; fi
start_follower
trap 'mark "ABORT signal"; [ -n "$KMSG_PID" ] && kill "$KMSG_PID" 2>/dev/null; exit 0' TERM INT

step0 || { pkill -P "$KMSG_PID" 2>/dev/null; kill "$KMSG_PID" 2>/dev/null; exit 0; }
[ "$limit" -ge 1 ] && { step1 || true; } || mark "SKIP step 1 (died there last time)"
[ "$limit" -ge 2 ] && { step2 || true; } || mark "SKIP step 2 (died there last time)"
mark DONE
sleep 5
pkill -P "$KMSG_PID" 2>/dev/null; kill "$KMSG_PID" 2>/dev/null
flush
exit 0
