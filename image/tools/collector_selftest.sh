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
echo "collector selftest OK"
