# Sensors (SSC over hexagonrpcd + libssc + iio-sensor-proxy). Read-only: no service start or stop, no remoteproc
# action (resetting the ADSP crashes the SoC), no raw sensor values: names, counts, states and log lines only.
# Output goes to extra-sensors.txt.
root=/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11
state=/var/lib/hexagonrpcd/registry
echo "## packages"
rpm -q hexagonrpcd libssc libssc-tools iio-sensor-proxy sp11-sensors fastrpc fastrpc-services qrtr 2>&1
echo
echo "## nodes and remoteprocs"
ls -l /dev/fastrpc-* 2>&1
for d in /sys/class/remoteproc/remoteproc*; do echo "$(basename $d)=$(cat $d/name 2>&1):$(cat $d/state 2>&1)"; done
echo
echo "## units"
for u in hexagonrpcd-sensors.service hexagonrpcd-sensors-sleep.service iio-sensor-proxy.service adsprpcd.service adsprpcd_audiopd.service; do
	echo "$u: enabled=$(systemctl is-enabled $u 2>&1) active=$(systemctl is-active $u 2>&1) restarts=$(systemctl show -p NRestarts --value $u 2>&1)"
done
echo
echo "## served tree (counts and names only)"
echo "sns_reg.conf: $(ls -l $root/sensors/sns_reg.conf 2>&1)"
echo "config files: $(ls $root/sensors/config 2>/dev/null | wc -l)"
echo "socinfo: $(ls $root/socinfo 2>&1 | tr '\n' ' ')"
echo "registry link: $(ls -ld $root/sensors/registry 2>&1)"
echo "registry parent entries: $(ls "$state" 2>/dev/null | wc -l)"
echo "registry child: $(ls -ld "$state/registry" 2>&1)"
echo "registry child regular files: $(find "$state/registry" -maxdepth 1 -type f 2>/dev/null | wc -l)"
find "$state/registry" -maxdepth 1 -type f -printf '%u:%g %m\n' 2>/dev/null | sort | uniq -c
echo "node udev properties:"
udevadm info --query=property --name=/dev/fastrpc-adsp 2>&1 | grep -E '^(DEVNAME|IIO_SENSOR_PROXY_TYPE|SYSTEMD_WANTS|TAGS)=' || :
pid=$(systemctl show -p MainPID --value hexagonrpcd-sensors.service 2>/dev/null)
case "$pid" in ''|0|*[!0-9]*) echo "daemon process unavailable";; *) grep -E '^(Uid|Gid|Groups|NoNewPrivs|Seccomp|Seccomp_filters):' "/proc/$pid/status" 2>&1;; esac
systemctl show hexagonrpcd-sensors.service iio-sensor-proxy.service -p ActiveState -p SubState -p Result -p ExecMainCode -p ExecMainStatus -p MainPID -p NRestarts 2>&1
echo "ADSP-written state files: $(ls -l $state/sns_reg_config $state/sns_secure_database.bin $state/parsed_file_list.csv 2>&1)"
echo "newest registry files: $(ls -lt $state 2>/dev/null | sed -n '2,6p' | awk '{print $5, $6, $7, $8, $9}' | tr '\n' ';')"
echo
echo "## qrtr services"
timeout 5 qrtr-lookup 2>&1 | head -n 60
echo
echo "## hexagonrpcd journal (this boot)"
journalctl -b -u hexagonrpcd-sensors.service --no-pager 2>&1 | tail -n 80
echo
echo "## iio-sensor-proxy journal (this boot)"
journalctl -b -u iio-sensor-proxy.service --no-pager 2>&1 | tail -n 60
echo
echo "## dmesg: fastrpc and ADSP"
timeout 8 dmesg --time-format=iso 2>&1 | grep -i -E 'fastrpc|adsp|sensorspd|qrtr' | tail -n 80
echo
echo "## proxy output counts (monitor-sensor 6 s, numbers masked)"
if command -v monitor-sensor >/dev/null 2>&1; then
	timeout 6 monitor-sensor 2>&1 | sed -E 's/-?[0-9]+([.,][0-9]+)?/N/g' | sort | uniq -c
else
	echo "monitor-sensor not installed"
fi
echo
echo "## tablet mode switch (SSAM)"
for d in /sys/class/input/input*; do n=$(cat $d/name 2>/dev/null); case "$n" in *"Tablet Mode Switch"*) echo "$(basename $d): $n sw-capability=$(cat $d/capabilities/sw)";; esac; done
true
