# dsp-subsystems drop-in for sp11-log-collector (image request R-I1).
# Install as /etc/sp11-log-collector.d/dsp-subsystems.sh. The collector sources it in a subshell at every
# snapshot and writes stdout and stderr to extra-dsp-subsystems.txt. No timeout is applied by the collector,
# so every command here carries its own.
#
# Read-only: it reads sysfs, debugfs, /proc and the kernel log, and runs qrtr-lookup (one name-service query
# on an AF_QIPCRTR socket). It writes nothing, loads no module, never touches a charger or battery attribute
# except by reading it (S3, S6).

T() { timeout 8 "$@" 2>&1; }
R() { timeout 3 cat "$1" 2>&1 | tr '\n\000' '  '; }

echo "## time"
date -u +%FT%TZ
echo "uptime: $(cut -d' ' -f1 /proc/uptime)"

echo
echo "## remoteproc: name state firmware recovery coredump, owner device, driver"
for r in /sys/class/remoteproc/remoteproc*; do
	[ -d "$r" ] || continue
	dev=$(basename "$(readlink -f "$r/device" 2>/dev/null)")
	drv=$(basename "$(readlink -f "$r/device/driver" 2>/dev/null)")
	echo "$(basename "$r"): name=$(R "$r/name") state=$(R "$r/state") firmware=$(R "$r/firmware") recovery=$(R "$r/recovery") coredump=$(R "$r/coredump") device=$dev driver=$drv"
done

echo
echo "## remoteproc debugfs (name, recovery)"
for d in /sys/kernel/debug/remoteproc/remoteproc*; do
	[ -d "$d" ] || continue
	echo "$(basename "$d"): name=$(R "$d/name") recovery=$(R "$d/recovery")"
done

echo
echo "## debugfs entries that exist for these subsystems (qcom_pdr* does not exist in 7.3: no debugfs in pdr_interface.c or qcom_pd_mapper.c)"
T ls /sys/kernel/debug | grep -i -E 'qcom|pdr|rproc|remoteproc|glink|qrtr|smem|rpmsg|pmic' || echo "(none)"
for f in /sys/kernel/debug/qcom_stats/adsp /sys/kernel/debug/qcom_stats/cdsp; do
	[ -r "$f" ] && { echo "== $f"; T cat "$f"; }
done

echo
echo "## platform devices: remoteproc and pmic-glink, with bound driver"
for d in /sys/bus/platform/devices/*remoteproc* /sys/bus/platform/devices/pmic-glink; do
	[ -e "$d" ] || continue
	echo "$(basename "$d"): driver=$(basename "$(readlink -f "$d/driver" 2>/dev/null)")"
done

echo
echo "## auxiliary devices (pd-mapper, pmic_glink clients) and drivers"
for d in /sys/bus/auxiliary/devices/*; do
	[ -e "$d" ] || continue
	echo "$(basename "$d"): driver=$(basename "$(readlink -f "$d/driver" 2>/dev/null)")"
done

echo
echo "## rpmsg devices (GLINK channels): name, driver"
for d in /sys/bus/rpmsg/devices/*; do
	[ -e "$d" ] || continue
	echo "$(basename "$d"): name=$(R "$d/name") driver=$(basename "$(readlink -f "$d/driver" 2>/dev/null)")"
done

echo
echo "## device nodes"
T ls -l /dev/fastrpc-* /dev/rpmsg* /dev/qrtr* /dev/remoteproc* || true

echo
echo "## qrtr-lookup (nodes, services, versions, instances)"
if command -v qrtr-lookup >/dev/null 2>&1; then
	T qrtr-lookup
else
	echo "qrtr-lookup: not installed"
fi

echo
echo "## deferred probes that name the DSP stack"
grep -i -E 'remoteproc|q6v5|glink|pmic|qrtr|pdr|pd-mapper|fastrpc|apr|gpr|smp2p|aoss|ipcc|ucsi|typec|battmgr' /sys/kernel/debug/devices_deferred 2>&1 || echo "(none)"

echo
echo "## loaded modules of the stack"
grep -E '^(qcom_q6v5|qcom_q6v5_pas|qcom_pd_mapper|pdr_interface|qcom_pdr_msg|qmi_helpers|qrtr|qrtr_smd|qrtr_mhi|qcom_glink|qcom_glink_smem|qcom_smem|smp2p|qcom_sysmon|qcom_common|qcom_pil_info|mdt_loader|qcom_aoss|qcom_ipcc|pmic_glink|pmic_glink_altmode|qcom_battmgr|ucsi_glink|typec_ucsi|fastrpc|apr|rpmsg_core|rpmsg_char|rpmsg_ctrl|qcom_pmic_pdcharger_ulog|snd_soc_qcom_common|q6apm|q6prm|ps883x) ' /proc/modules 2>&1

echo
echo "## kernel log, DSP stack and firmware (full dmesg is in dmesg.txt)"
dmesg --time-format=iso 2>&1 | grep -i -E 'remoteproc|q6v5|qcom_q6v5_pas|glink|qcom_smd_qrtr|qrtr|PDR|PDM:|pd-mapper|pd_mapper|pmic_glink|pmic-glink|qcom_battmgr|battmgr|ucsi|altmode|fastrpc|sysmon|ssctl|smp2p|aoss|mdt_loader|minidump|Direct firmware|request_firmware|failed to create endpoint|failed to announce|failed while handling|handling crash|crash detected|recovering|watchdog received|fatal error|gprsvc|qcom-apm|qcom-prm|CMD timeout|apr' | head -n 400

echo
echo "## systemd units of the stack"
T systemctl list-units --all --no-pager --no-legend 'rmtfs*' 'tqftpserv*' 'qrtr*' 'pd-mapper*' 'upower*' 'fastrpc*' 'adsprpcd*' 'cdsprpcd*' 'sdsprpcd*' || true

echo
echo "## power_supply: every supply, the attributes that matter (read only)"
for p in /sys/class/power_supply/*; do
	[ -d "$p" ] || continue
	echo "== $(basename "$p") ($(readlink -f "$p" | sed 's|/sys/devices/||'))"
	for a in type status present online scope capacity capacity_level health technology cycle_count voltage_now voltage_min_design voltage_max_design current_now current_max power_now energy_now energy_full energy_full_design charge_now charge_full charge_full_design charge_type usb_type temp charge_control_start_threshold charge_control_end_threshold manufacturer model_name; do
		[ -r "$p/$a" ] && echo "  $a: $(R "$p/$a")"
	done
done

echo
echo "## upower (read only)"
if command -v upower >/dev/null 2>&1; then
	T upower -e
	for d in $(timeout 8 upower -e 2>/dev/null | grep -i -E 'battery|line_power'); do echo "-- $d"; T upower -i "$d"; done
fi

echo
echo "## typec and PD class devices that pmic-glink creates"
T ls -l /sys/class/typec /sys/class/usb_power_delivery || true

echo
echo "## glink trace (only when the entry has trace_event=:mod:qcom_glink on its command line)"
if [ -r /sys/kernel/tracing/trace ]; then
	grep -c . /sys/kernel/tracing/trace 2>&1
	timeout 8 grep -E 'qcom_glink_cmd_(open|open_ack|close|close_ack|version|version_ack)' /sys/kernel/tracing/trace 2>&1 | head -n 300
else
	echo "(tracefs not readable)"
fi
