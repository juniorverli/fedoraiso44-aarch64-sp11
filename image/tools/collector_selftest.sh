#!/usr/bin/env bash
# Tests the publish, SEQ and size-cap logic of the log collector on a plain directory
# (the WSL2 build host cannot mount vfat). The real SP11LOGS/ESP mount path is tested by L1.
#   scripts/image-container.sh run /sp11/image/tools/collector_selftest.sh
set -euo pipefail
C=/sp11/image/overlay/usr/libexec/sp11-log-collector
T=/tmp/ctarget; rm -rf $T /run/sp11-logs
export SP11_TEST_TARGET=$T
for i in 1 2 3; do SP11_TEST_BOOT_ID=boot-$i "$C" once 2>&1 | tail -n1; done
echo "SEQ: $(for i in 1 2 3; do cat $T/boot-$i/SEQ; done | tr '\n' ' ')"
test "$(cat $T/boot-3/SEQ)" = 3
test -e $T/boot-3/COMPLETE
echo "--- ESP mode, cap 400 KiB: older boots must be deleted, current kept"
export SP11_TEST_KIND=esp CAP_ESP_KIB=400
SP11_TEST_BOOT_ID=boot-4 "$C" once 2>&1 | tail -n1
ls $T
du -sk $T
ls $T/boot-4 | head -5
test -e $T/boot-4/COMPLETE
# the cap must have removed the oldest boots first and kept the newest
test ! -e $T/boot-1
test -e $T/boot-4
echo "--- early display snapshot (D19): written first, no COMPLETE marker, display files present"
export SP11_TEST_KIND=logs
unset CAP_ESP_KIB
rm -rf /run/sp11-logs
SP11_TEST_BOOT_ID=boot-early "$C" early 2>&1 | tail -n1
for f in cmdline.txt entry.txt devices_deferred.txt device_component.txt drm-class-ls.txt lsmod.txt fb-state.txt clk-display.txt display-dmesg.txt drm-state.txt backlight.txt pinctrl-pmic.txt dpcd-tool.txt STATUS dmesg.txt; do
	test -e "$T/boot-early/$f" -o -e "$T/boot-early/$f.gz" || { echo "early snapshot lacks $f"; exit 1; }
done
test ! -e $T/boot-early/COMPLETE
grep -q 'early display snapshot' $T/boot-early/STATUS
echo "--- S4: the Windows-disk guard and the PKNAME rule, with real loop devices"
D=/var/tmp/s4; rm -rf $D; mkdir -p $D
/sp11/image/tools/make-decoy-disk.sh $D/fake-windows.img >/dev/null
truncate -s 64M $D/stick.img; sgdisk -n1:2048:+30M -t1:0700 $D/stick.img >/dev/null
mkfs.vfat -F 32 -n SP11LOGS --offset 2048 $D/stick.img >/dev/null 2>&1
LW=$(losetup -fP --show $D/fake-windows.img); LS=$(losetup -fP --show $D/stick.img)
for L in $LW $LS; do b=$(basename $L); for p in /sys/block/$b/${b}p*; do n=$(basename $p); [ -e /dev/$n ] || mknod /dev/$n b $(tr : " " < $p/dev); done; done
SP11_MSR_GUID=e6d6d379-f507-44c2-a23c-238f2a3df928
eval "$(sed -n '/^pkname() {/,/^}/p;/^disk_has_windows() {/,/^}/p;/^on_boot_disk() {/,/^}/p' "$C")"
disk_has_windows "$(basename $LW)" || { echo "guard missed the fake Windows disk"; exit 1; }
disk_has_windows "$(basename $LS)" && { echo "guard refused a clean stick"; exit 1; }
test "$(pkname ${LW}p1)" = "$(basename $LW)" -a "$(pkname $LW)" = "$(basename $LW)"
# a partition labelled SP11LOGS exists on the fake Windows disk and on the stick: only the stick's is on the boot disk
BOOT_DISK=$(basename $LS)
got=$(on_boot_disk SP11LOGS || true); echo "on_boot_disk SP11LOGS with boot disk $BOOT_DISK -> ${got:-nothing}"
case $got in *"$(basename $LW)"*) echo "PKNAME rule picked the fake Windows disk"; exit 1 ;; esac
BOOT_DISK=$(basename $LW)
got=$(on_boot_disk BOOT || true); case $got in "") echo "FAIL: expected the decoy BOOT only when it is the boot disk";; esac
BOOT_DISK=nosuchdisk; on_boot_disk BOOT && { echo "PKNAME rule returned a partition for an unknown disk"; exit 1; }
losetup -d $LW $LS
echo "S4 guard selftest OK"
echo "collector selftest OK"
