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
# readlink -f can succeed for a missing final component and print "driver".
# Require the link target to exist so an unbound device is explicit.
D() {
	link=$(readlink -e "$1/driver" 2>/dev/null) || { echo unbound; return; }
	basename "$link"
}

echo "## time"
date -u +%FT%TZ
echo "uptime: $(cut -d' ' -f1 /proc/uptime)"

echo
echo "## remoteproc: name state firmware recovery coredump, owner device, driver"
for r in /sys/class/remoteproc/remoteproc*; do
	[ -d "$r" ] || continue
	dev=$(basename "$(readlink -f "$r/device" 2>/dev/null)")
	drv=$(D "$r/device")
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
	echo "$(basename "$d"): driver=$(D "$d")"
done

echo
echo "## auxiliary devices (pd-mapper, pmic_glink clients) and drivers"
for d in /sys/bus/auxiliary/devices/*; do
	[ -e "$d" ] || continue
	echo "$(basename "$d"): driver=$(D "$d")"
done

echo
echo "## rpmsg devices (GLINK channels): name, driver"
for d in /sys/bus/rpmsg/devices/*; do
	[ -e "$d" ] || continue
	echo "$(basename "$d"): name=$(R "$d/name") driver=$(D "$d")"
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
echo "## IPCC, SMP2P and GLINK interrupt counts"
grep -i -E 'ipcc|glink-smem|smp2p-(adsp|cdsp)|q6v5' /proc/interrupts 2>&1 || true

echo
echo "## D23 battery policy (configuration and dry run only)"
T modprobe --showconfig | grep -E '^(blacklist|install) qcom_battmgr( |$)' || true
T modprobe -n -v qcom_battmgr

echo
echo "## kernel log, DSP stack and firmware (full dmesg is in dmesg.txt)"
dmesg --time-format=iso 2>&1 | grep -i -E 'remoteproc|q6v5|qcom_q6v5_pas|glink|qcom_smd_qrtr|qrtr|PDR|PDM:|pd-mapper|pd_mapper|pmic_glink|pmic-glink|qcom_battmgr|battmgr|ucsi|altmode|fastrpc|sysmon|ssctl|smp2p|aoss|mdt_loader|minidump|Direct firmware|request_firmware|failed to create endpoint|failed to announce|failed while handling|handling crash|crash detected|recovering|watchdog received|fatal error|gprsvc|qcom-apm|qcom-prm|CMD timeout|apr' | head -n 400

echo
echo "## systemd units of the stack"
T systemctl list-units --all --no-pager --no-legend 'rmtfs*' 'tqftpserv*' 'qrtr*' 'pd-mapper*' 'upower*' 'fastrpc*' 'adsprpcd*' 'cdsprpcd*' 'sdsprpcd*' || true
T systemctl show upower.service -p LoadState -p ActiveState -p SubState -p Result -p ExecMainStatus
T journalctl -b -u upower.service --no-pager -n 60

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
echo "## GLINK trace configuration (read only; collector never enables or clears tracing)"
T cat /proc/cmdline
for f in tracing_on trace_clock buffer_size_kb events/qcom_glink/enable; do
	[ -r "/sys/kernel/tracing/$f" ] && echo "$f: $(R "/sys/kernel/tracing/$f")"
done
for f in /sys/kernel/tracing/events/qcom_glink/qcom_glink_cmd_*/enable; do
	[ -r "$f" ] && echo "$(basename "$(dirname "$f")"): $(R "$f")"
done
for f in /sys/kernel/tracing/per_cpu/cpu*/stats; do
	[ -r "$f" ] || continue
	echo "== $f"
	T cat "$f"
done

echo
echo "## GLINK control handshake, separately per edge (no payload data)"
if [ -r /sys/kernel/tracing/trace ]; then
	for edge in cdsp lpass; do
		echo "== $edge"
		timeout 8 grep -E "qcom_glink_cmd_(open|open_ack|close|close_ack|version|version_ack):.*remote: $edge " /sys/kernel/tracing/trace 2>&1 | head -n 300
	done
else
	echo "(tracefs not readable)"
fi

echo
echo "## SMP2P, AOSS, RPMh and genpd trace (read only; system names in 7.3: qcom_smp2p, qcom_aoss, rpmh, power)"
for f in events/qcom_smp2p/enable events/qcom_aoss/enable events/rpmh/enable events/power/power_domain_target/enable; do
	[ -r "/sys/kernel/tracing/$f" ] && echo "$f: $(R "/sys/kernel/tracing/$f")"
done
if [ -r /sys/kernel/tracing/trace ]; then
	echo "== qcom_smp2p (all edges; names carry the edge)"
	timeout 8 grep -E " (smp2p_[a-z_]+):" /sys/kernel/tracing/trace 2>&1 | head -n 200
	echo "== qcom_aoss (load_state and other QMP sends)"
	timeout 8 grep -E " aoss_send(_done)?:" /sys/kernel/tracing/trace 2>&1 | grep -v "res: qdss" | head -n 100
	echo "qdss clock sends (count only): $(timeout 8 grep -c 'res: qdss' /sys/kernel/tracing/trace 2>&1)"
	echo "== genpd performance state (nsp, mxc, cx)"
	timeout 8 grep -E " power_domain_target:.*(nsp|mxc|cx)" /sys/kernel/tracing/trace 2>&1 | head -n 100
	echo "== rpmh sends (counts only, can be large)"
	timeout 8 grep -c -E " rpmh_send_msg:" /sys/kernel/tracing/trace 2>&1
else
	echo "(tracefs not readable)"
fi

echo
echo "## handover and proxy power domain state (patch 0003 log, genpd)"
T dmesg | grep -E "handover: proxy power domains|remoteproc[0-9]+: (powering up|remote processor)" | head -n 20
for d in nsp mxc cx; do
	grep -E "^$d " /sys/kernel/debug/pm_genpd/pm_genpd_summary 2>/dev/null
done

echo
echo "## DSP firmware build ids actually loaded (M14: compare with the denisix reference, c1-00046.1)"
for f in /lib/firmware/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn /usr/lib/firmware/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn \
	/lib/firmware/qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn; do
	[ -r "$f" ] || continue
	echo "$f $(timeout 8 sha256sum "$f" | cut -c1-16) $(timeout 8 strings -n 8 "$f" | grep -m1 '^QC_IMAGE_VERSION_STRING=')"
done
echo "firmware_class.path: $(R /sys/module/firmware_class/parameters/path)"
echo "cmdline firmware/pas args: $(tr ' ' '\n' </proc/cmdline | grep -E '^(firmware_class|qcom_q6v5_pas)\.' | tr '\n' ' ')"
