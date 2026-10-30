# Drop-in for /etc/sp11-log-collector.d/ec-sam.sh (sourced by sp11-log-collector).
# Read-only: sysfs reads and dmesg filters. No input events, no serials, no writes.
echo "== SAM kernel messages (all boot) =="
dmesg 2>/dev/null | grep -iE 'ssam|surface_|aggregator|surface_hid|serial1|ttyHS0' |
	grep -vE 'input: |spi 045E' | cut -c1-200
echo
echo "== SAM serdev/platform hub driver binding =="
for p in /sys/bus/serial/devices/* /sys/bus/platform/devices/surface_aggregator_platform_hub* /sys/bus/surface_aggregator/devices/*; do
	[ -e "$p" ] || continue
	drv=$(basename "$(readlink -f "$p/driver" 2>/dev/null)")
	echo "$(basename "$p") driver=${drv:-none}"
done
echo
echo "== Surface input nodes: name, bus device (no events read) =="
for e in /sys/class/input/event*; do
	n=$(cat "$e/device/name" 2>/dev/null)
	case "$(readlink -f "$e/device")" in
	*surface_aggregator_platform_hub*) echo "$(basename "$e") $n runtime_status=$(cat "$e/device/power/runtime_status" 2>/dev/null)" ;;
	esac
done
echo
echo "== Surface hidraw count and runtime PM of serdev =="
ls /sys/class/hidraw 2>/dev/null | wc -l
for d in /sys/bus/serial/devices/*; do
	[ -e "$d/power/runtime_status" ] && echo "$(basename "$d") $(cat "$d/power/runtime_status")"
done
echo
echo "== Interrupt counts: SAM wake/RX lines (counts only) =="
grep -iE 'b88000|surface|ssam' /proc/interrupts 2>/dev/null | awk '{print $1, $NF, $(NF-1)}'
echo
echo "== Boot kind markers =="
cat /proc/cmdline | tr ' ' '\n' | grep -E '^sp11\.' ; cat /proc/sys/kernel/random/boot_id | cut -c1-8
echo "dmesg first line:"; dmesg 2>/dev/null | head -1 | cut -c1-60
