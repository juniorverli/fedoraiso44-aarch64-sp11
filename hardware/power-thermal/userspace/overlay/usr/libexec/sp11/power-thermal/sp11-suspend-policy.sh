#!/usr/bin/bash
# sp11-suspend-policy.sh lid|wakeup : opt-in policies, selected by units that test the kernel command line.
#   lid     write a logind drop-in under /run (never /etc): lid close suspends, as in stock Fedora.
#   wakeup  keep only the power button and the lid switch as wake sources (the Ubuntu SP11 report saw
#           spurious wakes from touch, pen and other gpio sources). SAM (Type Cover) wake stays as the
#           driver leaves it: disabled. sp11.wakeup_policy=cover also enables the SAM wake line.
# Both only narrow behaviour; neither touches a thermal or charging limit.
set -u
export LC_ALL=C PATH=/usr/sbin:/usr/bin:/sbin:/bin
case ${1:-} in
lid)
	mkdir -p /run/systemd/logind.conf.d
	cat >/run/systemd/logind.conf.d/60-sp11-lid-suspend.conf <<'CONF'
[Login]
HandleLidSwitch=suspend
HandleLidSwitchExternalPower=suspend
HandleLidSwitchDocked=ignore
CONF
	logger -t sp11-suspend-policy "lid close will suspend (sp11.suspend_lid)"
	;;
wakeup)
	mode=$(sed -n 's/.*sp11\.wakeup_policy=\([a-z-]*\).*/\1/p' /proc/cmdline)
	off=0 keep=0
	for w in $(find /sys/devices -path '*/power/wakeup' 2>/dev/null); do
		d=${w%/power/wakeup}
		[ "$(cat "$w" 2>/dev/null)" = enabled ] || continue
		case "$d" in
		*pwrkey* | */gpio-keys*) keep=$((keep + 1)); continue ;;
		esac
		echo disabled >"$w" 2>/dev/null && off=$((off + 1))
	done
	if [ "$mode" = cover ]; then
		for s in /sys/bus/serial/devices/*; do
			[ "$(basename "$(readlink -f "$s/driver" 2>/dev/null)")" = surface_serial_hub ] && echo enabled >"$s/power/wakeup" 2>/dev/null
		done
	fi
	logger -t sp11-suspend-policy "wake sources: kept $keep, disabled $off (mode=${mode:-pwrkey-lid})"
	;;
*)
	echo "usage: $0 lid|wakeup" >&2
	exit 2
	;;
esac
