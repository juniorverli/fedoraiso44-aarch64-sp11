# Drop-in for /etc/sp11-log-collector.d/power-thermal.sh (sourced by sp11-log-collector, output goes to
# extra-power-thermal.txt). Strictly read-only: sysfs/debugfs reads, no writes, no suspend, no events.
# Every read has a timeout: SAM hwmon reads are UART requests and must never hang the snapshot.
rd() { timeout 3 cat "$1" 2>&1 | tr '\n' ' '; }
rdl() { local v; v=$(timeout 3 cat "$1" 2>/dev/null | tr '\n' ' '); printf '%s' "${v:-?}"; }

echo "== power-thermal collector v1 (read-only) =="
echo "kernel: $(uname -r)"
echo "cmdline sp11/pm tokens:"
tr ' ' '\n' </proc/cmdline | grep -E '^(sp11\.|mem_sleep_default|no_console_suspend|printk\.console_suspend|pm_debug_messages)' | sed 's/^/  /'

echo
echo "== suspend capability =="
for f in state mem_sleep pm_test pm_debug_messages pm_print_times sync_on_suspend wakeup_count pm_wakeup_irq; do
	[ -e "/sys/power/$f" ] && echo "/sys/power/$f: $(rd /sys/power/$f)" || echo "/sys/power/$f: absent"
done
echo "-- suspend_stats"
for f in /sys/power/suspend_stats/*; do [ -f "$f" ] && echo "$(basename "$f"): $(rd "$f")"; done
echo "-- PM config (from running kernel)"
zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_(SUSPEND|PM_SLEEP|PM_DEBUG|PM_SLEEP_DEBUG|PM_ADVANCED_DEBUG|PSTORE|PSTORE_RAM|EFI_VARS_PSTORE|CPU_THERMAL|CPU_FREQ_THERMAL|DEVFREQ_THERMAL|QCOM_LMH|QCOM_TSENS|ARM_SCMI_CPUFREQ)=' ||
	grep -E '^CONFIG_(SUSPEND|PM_SLEEP|PM_DEBUG|PM_SLEEP_DEBUG|PSTORE|PSTORE_RAM|CPU_FREQ_THERMAL|QCOM_LMH|ARM_SCMI_CPUFREQ)=' "/boot/config-$(uname -r)" 2>/dev/null
echo "-- pstore"; ls -la /sys/fs/pstore 2>&1 | head -10
echo "-- effective sleep/logind config"
systemd-analyze cat-config systemd/sleep.conf systemd/logind.conf 2>&1 | grep -E '^(Handle|Allow|Suspend|Hibernate|MemorySleep|LidSwitch|Idle|# /)' | head -30

echo
echo "== wake sources (power/wakeup enabled or capable, from sysfs) =="
for w in $(find /sys/devices -path '*/power/wakeup' 2>/dev/null | sort); do
	v=$(rdl "$w")
	[ "$v" = "?" ] && continue
	case "$v" in *enabled*) tag=ENABLED ;; *) tag=disabled ;; esac
	d=${w%/power/wakeup}
	echo "$tag $(echo "$d" | sed 's#^/sys/devices/##' | cut -c1-110) driver=$(basename "$(readlink -f "$d/driver" 2>/dev/null)" 2>/dev/null)"
done | sort | uniq -c | sort -k2,2 | head -150
echo "-- wakeup_sources (class/wakeup: name active_count event_count wakeup_count)"
for w in /sys/class/wakeup/wakeup*; do
	[ -d "$w" ] || continue
	echo "$(rdl "$w/name") active=$(rdl "$w/active_count") events=$(rdl "$w/event_count") wakeups=$(rdl "$w/wakeup_count") abort=$(rdl "$w/expire_count")"
done | sort | head -60
echo "-- RTC (the DT marks the pmk8550 alarm as owned by the ADSP: qcom,no-alarm)"
for r in /sys/class/rtc/rtc*; do [ -d "$r" ] && echo "$(basename "$r") name=$(rdl "$r/name") wakealarm=$([ -e "$r/wakealarm" ] && echo present || echo absent)"; done
echo "-- lid / gpio-keys / pwrkey input devices (names only; no events read)"
for i in /sys/class/input/input*; do
	n=$(rdl "$i/name")
	case "$n" in *gpio-keys*|*pwrkey*|*pm8941*|*Lid*|*lid*) echo "$(basename "$i") $n sw=$(rdl "$i/capabilities/sw") key=$(rdl "$i/capabilities/key" | cut -c1-40)" ;; esac
done
echo "-- SAM serdev wakeup (default disabled by the driver)"
for s in /sys/bus/serial/devices/*; do [ -e "$s/power/wakeup" ] && echo "$(basename "$s") wakeup=$(rdl "$s/power/wakeup") runtime=$(rdl "$s/power/runtime_status")"; done
echo "-- wake-capable interrupts (/proc/interrupts lines with counters)"
grep -iE 'wake|pwrkey|gpio-keys|lid|ssam|wdog|thermal-sensor|temp-alarm' /proc/interrupts 2>/dev/null | cut -c1-140

echo
echo "== cpuidle: per CPU state name, disable, usage, time, s2idle usage/time =="
echo "driver=$(rdl /sys/devices/system/cpu/cpuidle/current_driver) governor=$(rdl /sys/devices/system/cpu/cpuidle/current_governor)"
for c in /sys/devices/system/cpu/cpu[0-9]*; do
	for s in "$c"/cpuidle/state*; do
		[ -d "$s" ] || continue
		echo "$(basename "$c")/$(basename "$s") name=$(rdl "$s/name") disable=$(rdl "$s/disable") usage=$(rdl "$s/usage") time=$(rdl "$s/time") above=$(rdl "$s/above") below=$(rdl "$s/below") s2idle_usage=$(rdl "$s/s2idle/usage") s2idle_time=$(rdl "$s/s2idle/time") exit_latency=$(rdl "$s/latency") residency=$(rdl "$s/residency")"
	done
done
echo "-- genpd idle-state residency (debugfs; cluster and system domains)"
for d in /sys/kernel/debug/pm_genpd/power-domain-*; do
	case "$d" in */power-domain-cpu[0-9]*) continue ;; esac
	[ -d "$d" ] && { echo "$(basename "$d") current_state=$(rdl "$d/current_state")"; timeout 3 cat "$d/idle_states" 2>&1 | head -6; }
done
echo "-- CPU online mask: $(rdl /sys/devices/system/cpu/online) possible: $(rdl /sys/devices/system/cpu/possible)"

echo
echo "== cpufreq =="
if [ -d /sys/devices/system/cpu/cpufreq ]; then
	for p in /sys/devices/system/cpu/cpufreq/policy*; do
		echo "$(basename "$p") cpus=$(rdl "$p/related_cpus") driver=$(rdl "$p/scaling_driver") gov=$(rdl "$p/scaling_governor") cur=$(rdl "$p/scaling_cur_freq") min=$(rdl "$p/scaling_min_freq") max=$(rdl "$p/scaling_max_freq") hw_min=$(rdl "$p/cpuinfo_min_freq") hw_max=$(rdl "$p/cpuinfo_max_freq")"
	done
else
	echo "NO /sys/devices/system/cpu/cpufreq: no cpufreq driver registered (M13 state)"
fi
echo "-- scmi/cpufreq module state"
lsmod | grep -iE 'scmi|cpufreq|lmh|tsens' ; ls /sys/bus/scmi_protocol/devices 2>&1 | head -20
for d in /sys/bus/scmi_protocol/devices/*; do [ -e "$d" ] && echo "$(basename "$d") driver=$(basename "$(readlink -f "$d/driver" 2>/dev/null)")"; done
dmesg 2>/dev/null | grep -iE 'cpufreq|scmi_cpufreq|lmh|opp' | cut -c1-200 | head -20

echo
echo "== thermal zones: type temp mode policy trips (mC) =="
for z in /sys/class/thermal/thermal_zone*; do
	[ -d "$z" ] || continue
	line="$(basename "$z") type=$(rdl "$z/type") temp=$(rdl "$z/temp") mode=$(rdl "$z/mode") policy=$(rdl "$z/policy")"
	for t in "$z"/trip_point_*_temp; do
		[ -e "$t" ] || continue
		b=${t%_temp}
		line="$line | $(rdl "${b}_type")=$(rdl "$t") hyst=$(rdl "${b}_hyst")"
	done
	echo "$line"
done
echo "-- cooling devices (cur/max state) and their zone bindings"
for c in /sys/class/thermal/cooling_device*; do [ -d "$c" ] && echo "$(basename "$c") type=$(rdl "$c/type") cur=$(rdl "$c/cur_state") max=$(rdl "$c/max_state")"; done
for z in /sys/class/thermal/thermal_zone*/cdev*_trip_point; do [ -e "$z" ] && echo "binding $(echo "$z" | sed 's#/sys/class/thermal/##') = $(rdl "$z")"; done
echo "-- thermal governors: $(rdl /sys/class/thermal/thermal_zone0/available_policies)"

echo
echo "== hwmon (name, temps, fan, power) =="
for h in /sys/class/hwmon/hwmon*; do
	[ -d "$h" ] || continue
	echo "$(basename "$h") name=$(rdl "$h/name") device=$(basename "$(readlink -f "$h/device" 2>/dev/null)")"
	for a in "$h"/temp*_input "$h"/fan*_input "$h"/power*_input "$h"/curr*_input "$h"/in*_input; do
		[ -e "$a" ] || continue
		b=${a%_input}
		echo "   $(basename "$a")=$(rdl "$a") label=$(rdl "${b}_label")"
	done
done

echo
echo "== power_supply (read-only attributes; writable charge controls are only flagged by file mode) =="
for p in /sys/class/power_supply/*; do
	[ -d "$p" ] || continue
	echo "-- $(basename "$p") type=$(rdl "$p/type") status=$(rdl "$p/status") online=$(rdl "$p/online") capacity=$(rdl "$p/capacity")"
	for a in energy_full_design energy_full energy_now voltage_now voltage_min_design power_now current_now current_max cycle_count capacity_level technology health charge_type usb_type; do
		[ -e "$p/$a" ] && echo "   $a=$(rdl "$p/$a")"
	done
	for a in "$p"/charge_control_* "$p"/charge_behaviour "$p"/charge_types "$p"/charge_term_current "$p"/constant_charge_* ; do
		[ -e "$a" ] && echo "   CHARGE-CONTROL $(basename "$a") mode=$(stat -c %a "$a") value=$(rdl "$a")"
	done
done
echo "-- qcom_battmgr loaded? (D23: must be absent) $(lsmod | grep -c '^qcom_battmgr')"
echo "-- upower summary (read-only, 3 s)"; timeout 3 upower -d 2>&1 | grep -iE 'native-path|state|percentage|energy|capacity|charge|threshold|battery-level' | head -24

echo
echo "== backlight and eDP state (no writes) =="
for b in /sys/class/backlight/*; do [ -d "$b" ] && echo "$(basename "$b") brightness=$(rdl "$b/brightness") actual=$(rdl "$b/actual_brightness") max=$(rdl "$b/max_brightness") bl_power=$(rdl "$b/bl_power") type=$(rdl "$b/type")"; done
for c in /sys/class/drm/card*-*; do [ -e "$c/status" ] && echo "$(basename "$c") status=$(rdl "$c/status") enabled=$(rdl "$c/enabled") dpms=$(rdl "$c/dpms")"; done

echo
echo "== remoteproc and DSP wake interrupts (counts only) =="
for r in /sys/class/remoteproc/remoteproc*; do [ -d "$r" ] && echo "$(basename "$r") name=$(rdl "$r/name") state=$(rdl "$r/state") recovery=$(rdl "$r/recovery")"; done
grep -iE 'wdog|fatal|ready|handover|stop-ack|glink|smp2p' /proc/interrupts 2>/dev/null | cut -c1-140
dmesg 2>/dev/null | grep -iE 'remoteproc|crash|recovery|wdog|fastrpc' | cut -c1-180 | tail -12

echo
echo "== suspend/resume traces left by the SP11 units (this boot) =="
for f in /run/sp11-suspend-diag/ladder.log /run/sp11-suspend-diag/hook.log; do
	[ -f "$f" ] && { echo "--- $f"; tail -n 400 "$f"; }
done
echo "== thermal sampler tail (this boot) =="
[ -f /run/sp11-thermal/thermal.csv ] && { head -1 /run/sp11-thermal/thermal.csv; tail -n 120 /run/sp11-thermal/thermal.csv; } || echo "sampler not running (add sp11.thermal_log=1 to the kernel line)"
