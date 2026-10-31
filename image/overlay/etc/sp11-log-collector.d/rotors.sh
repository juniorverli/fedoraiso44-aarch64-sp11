# M15 Linux-side experiments and boot-medium state (image-owned). Read-only. One file: what the SAM rotor, the CDSP experiment, the identity
# switch and the cpufreq cap did on this boot, the state files on the boot medium (GRUB is static and holds none), and the cpufreq registration.
echo "## cmdline tokens (the identity switch may append sp11.identity=none to /proc/cmdline; the real line is in /run/sp11/cmdline-kernel)"
tr ' ' '\n' </proc/cmdline | grep -E '^(sp11\.|firmware_class\.|qcom_q6v5_pas\.|surface_aggregator\.|trace_event=)' | sed 's/^/  /'
echo
echo "## SAM shutdown mode rotor (sp11-sam-mode-rotor.service)"
cat /run/sp11/sam-mode 2>&1
echo "module parameter now: $(cat /sys/module/surface_aggregator/parameters/shutdown_mode 2>&1)"
echo
echo "## CDSP experiment (sp11-cdsp-experiment.service; runtime restart of the CDSP, state in a file on the boot medium)"
cat /run/sp11/cdsp-experiment 2>&1
echo "-- sp11-glink and cdsp kernel lines after the restart"
cat /run/sp11/cdsp-experiment-dmesg.txt 2>&1 | tail -n 30
echo "remoteproc: $(for d in /sys/class/remoteproc/remoteproc*; do echo -n "$(basename $d)=$(cat $d/name 2>/dev/null):$(cat $d/state 2>/dev/null):$(cat $d/firmware 2>/dev/null) "; done)"
echo "keep_proxy_pds now: $(cat /sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds 2>&1) (writable: $( [ -w /sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds ] && echo yes || echo no ))"
echo "firmware_class.path now: '$(cat /sys/module/firmware_class/parameters/path 2>&1)'"
d=/usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali
echo "alternate pair installed: $( [ -s $d/qccdsp8380.mbn ] && [ -s $d/cdsp_dtb.mbn ] && echo yes || echo no ) (hashes: $(sha256sum $d/qccdsp8380.mbn $d/cdsp_dtb.mbn 2>/dev/null | cut -c1-12 | tr '\n' ' '))"
echo "default pair hashes: $(sha256sum /usr/lib/firmware/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn /usr/lib/firmware/qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn 2>/dev/null | cut -c1-12 | tr '\n' ' ')"
echo
echo "## GPU two-step (M15: skipped; unit installed disabled)"
echo "sp11-gpu-two-step.service: enabled=$(systemctl is-enabled sp11-gpu-two-step.service 2>&1) active=$(systemctl is-active sp11-gpu-two-step.service 2>&1)"
cat /run/sp11/gpu-test 2>&1
echo
echo "## identity switch (marker sp11/identity-none on the boot medium)"
cat /run/sp11/identity-switch 2>&1
echo
echo "## boot medium state (plain files, sp11-boot-state; markers are operator switches)"
timeout 20 /usr/libexec/sp11-boot-state list 2>&1 | head -n 20
echo "markers: $(timeout 20 /usr/libexec/sp11-boot-state markers 2>&1 | tr '\n' ' ')"
echo
echo "## operator notices of this boot"
cat /run/sp11/notice.d/*.txt 2>&1
echo
echo "## cpufreq (M15: scmi_cpufreq loaded by modules-load.d; cap only with the marker sp11/enable-cpufreq-cap)"
cat /run/sp11/cpufreq-cap 2>&1
systemctl is-active systemd-modules-load.service 2>&1 | sed "s/^/modules-load: /"
echo "cpufreq dir: $(ls /sys/devices/system/cpu/cpufreq 2>&1 | tr '\n' ' ')"
echo "scmi/cpufreq modules loaded: $(lsmod | grep -i -E 'scmi|cpufreq' | awk '{print $1}' | tr '\n' ' ')"
echo "scmi_cpufreq module present: $(find /lib/modules/$(uname -r) -name 'scmi*cpufreq*' -o -name 'scmi-cpufreq*' 2>/dev/null | head -n 3 | tr '\n' ' ')"
echo "scmi protocol devices: $(ls /sys/bus/scmi_protocol/devices 2>&1 | tr '\n' ' ')"
echo "cooling devices: $(ls /sys/class/thermal 2>&1 | grep -c cooling_device)"
timeout 8 dmesg 2>&1 | grep -i -E 'scmi|cpufreq|cpu freq' | head -n 20
true
