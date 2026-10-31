#!/bin/bash
# Read-only volume button test for patch 0005 (gpio-keys node "volume-keys").
# Run as root on the device. Two 10 s phases need the operator:
#   phase UP:   press only the volume UP button repeatedly (about 5 times)
#   phase DOWN: press only the volume DOWN button repeatedly (about 5 times)
# It only reads: /proc, debugfs and input events of the volume-keys device
# (never of the keyboard). It writes nothing to GPIO, pinctrl or sysfs.
# Output goes to stdout; redirect it into the log set. Private data: none.
set -u
secs=${SECS:-10}
echo "== kernel: $(uname -r), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id) =="

echo "== gpio-keys platform devices and their input devices =="
for d in /sys/bus/platform/drivers/gpio-keys/*; do
	[ -L "$d" ] || continue
	echo "bound: $(basename "$d")"
done
dev=
for e in /sys/class/input/event*; do
	[ -e "$e" ] || continue
	case "$(readlink -f "$e/device")" in
	*volume-keys*)
		dev=/dev/input/$(basename "$e")
		echo "volume-keys input: $dev name=$(cat "$e/device/name") caps_key=$(cat "$e/device/capabilities/key")"
		;;
	esac
done
[ -n "$dev" ] || echo "NO volume-keys input device (node not probed or gpio-keys not loaded)"

echo
echo "== dmesg: gpio-keys and PMIC GPIO lines =="
dmesg 2>/dev/null | grep -iE 'gpio-keys|volume-keys|key-volume|pmic_gpio|spmi-gpio|pinctrl.*pm8550' | cut -c1-200

echo
echo "== pm8550 pin configuration for gpio6 and gpio8 (debugfs, read only) =="
for d in /sys/kernel/debug/pinctrl/*; do
	case "$d" in *spmi*pmic@1*gpio@8800*|*pmic@1*gpio@8800*) ;; *) continue ;; esac
	echo "controller: $(basename "$d")"
	for f in pinconf-pins pins; do
		[ -r "$d/$f" ] && grep -E 'pin (5|7) |gpio6\b|gpio8\b' "$d/$f" | cut -c1-200
	done
done

snap() {
	grep -E 'key-volume|Volume (Up|Down)|volume-keys' /sys/kernel/debug/gpio 2>/dev/null |
		sed 's/  */ /g'
}
irqs() { grep -iE 'volume|key-vol' /proc/interrupts | awk '{n=0; for(i=2;i<=NF;i++) if ($i ~ /^[0-9]+$/) n+=$i; print $1, n, $NF}'; }

echo
echo "== idle snapshot (buttons released): GPIO state and IRQ counts =="
snap; irqs

phase() {
	name=$1
	echo
	echo "== PHASE $name: press ONLY the volume $name button for ${secs} s, starting now =="
	if [ -n "$dev" ] && command -v libinput >/dev/null; then
		timeout "$secs" libinput debug-events --show-keycodes --device "$dev" 2>&1 |
			grep -E 'KEYBOARD_KEY|DEVICE_ADDED|Error|error' &
	elif [ -n "$dev" ] && command -v evtest >/dev/null; then
		timeout "$secs" evtest "$dev" 2>&1 | grep -E 'type 1 \(EV_KEY\)' &
	fi
	end=$((SECONDS + secs))
	last=
	while [ "$SECONDS" -lt "$end" ]; do
		cur=$(snap)
		if [ "$cur" != "$last" ]; then
			echo "t=$SECONDS pin states: $cur" | tr '\n' ';'
			echo
			last=$cur
		fi
		sleep 0.1
	done
	wait
	echo "-- IRQ counts after $name:"
	irqs
}
phase UP
phase DOWN

echo
echo "== final snapshot =="
snap; irqs
echo "Expected if mapping is right: PHASE UP prints KEY_VOLUMEUP presses/releases and the"
echo "gpio-6 line (key-volume-up) toggles hi/lo only in PHASE UP; DOWN likewise with gpio-8."
echo "Swapped result: the opposite. No event in either phase with changing pin state:"
echo "wrong polarity or debounce; no pin change at all: wrong pin number."
