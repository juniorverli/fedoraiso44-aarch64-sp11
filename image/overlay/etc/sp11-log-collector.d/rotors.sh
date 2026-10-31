# M14 rotors and boot-medium state (image-owned). Read-only. One file: what the three rotors did on this boot, the GRUB environment block as the
# kernel line and sysfs show it, the GPU test result, and the cpufreq finding (M13 logs showed no cpufreq and so no cooling; no kernel change here).
echo "## cmdline tokens"
tr ' ' '\n' </proc/cmdline | grep -E '^(sp11\.|firmware_class\.|qcom_q6v5_pas\.|surface_aggregator\.|trace_event=)' | sed 's/^/  /'
echo
echo "## SAM shutdown mode rotor (sp11-sam-mode-rotor.service)"
cat /run/sp11/sam-mode 2>&1
echo "module parameter now: $(cat /sys/module/surface_aggregator/parameters/shutdown_mode 2>&1)"
echo
echo "## CDSP variant rotor (sp11-cdsp-variant.service)"
cat /run/sp11/cdsp-variant 2>&1
d=/usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali
echo "alternate pair installed: $( [ -s $d/qccdsp8380.mbn ] && [ -s $d/cdsp_dtb.mbn ] && echo yes || echo no ) (hashes: $(sha256sum $d/qccdsp8380.mbn $d/cdsp_dtb.mbn 2>/dev/null | cut -c1-12 | tr '\n' ' '))"
echo "default pair hashes: $(sha256sum /usr/lib/firmware/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn /usr/lib/firmware/qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn 2>/dev/null | cut -c1-12 | tr '\n' ' ')"
echo
echo "## GPU self-healing"
cat /run/sp11/gpu-test 2>&1
echo "DTB chosen by GRUB: $(tr ' ' '\n' </proc/cmdline | sed -n 's/^sp11.gpu_dtb=//p')"
echo
echo "## boot medium environment block (values GRUB will see at the next boot; empty = unset)"
timeout 20 /usr/libexec/sp11-esp-env list 2>&1 | grep -E '^(sp11_|#|sp11-esp-env)' | head -n 20
echo
echo "## operator notices of this boot"
cat /run/sp11/notice.d/*.txt 2>&1
echo
echo "## cpufreq (M14 note f: scmi_cpufreq missing in the M13 logs; the kernel is not changed here)"
echo "cpufreq dir: $(ls /sys/devices/system/cpu/cpufreq 2>&1 | tr '\n' ' ')"
echo "scmi/cpufreq modules loaded: $(lsmod | grep -i -E 'scmi|cpufreq' | awk '{print $1}' | tr '\n' ' ')"
echo "scmi_cpufreq module present: $(find /lib/modules/$(uname -r) -name 'scmi*cpufreq*' -o -name 'scmi-cpufreq*' 2>/dev/null | head -n 3 | tr '\n' ' ')"
echo "scmi protocol devices: $(ls /sys/bus/scmi_protocol/devices 2>&1 | tr '\n' ' ')"
echo "cooling devices: $(ls /sys/class/thermal 2>&1 | grep -c cooling_device)"
timeout 8 dmesg 2>&1 | grep -i -E 'scmi|cpufreq|cpu freq' | head -n 20
true
