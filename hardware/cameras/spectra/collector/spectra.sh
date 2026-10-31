# Spectra first test (TPG only, no sensor, no ICP). Read-only: no module load or unload, no ioctl on the camera
# nodes, no stream, no sensor power, no firmware request, no write to sysfs or debugfs. Names, counts and log lines
# only. Output goes to extra-spectra.txt. Run it after booting the m15-spectra entry; module loading is the
# entry's job (udev autoload from the OF aliases of Qualcomm's nodes, or a marker-file service of the image).
echo "## kernel and DT"
uname -r
tr '\0' ' ' < /proc/cmdline; echo
echo "model: $(tr -d '\0' < /proc/device-tree/model 2>&1)"
echo "compatible: $(tr '\0' ' ' < /proc/device-tree/compatible 2>&1)"
echo "Spectra DT active (soc@0/qcom,cam-cpas*): $(ls -d /proc/device-tree/soc@0/qcom,cam-cpas* 2>/dev/null | tr '\n' ' ')"
echo "camera-main node: $(ls -d /proc/device-tree/soc@0/qcom,camera-main 2>&1)"
echo "upstream camss status: $(tr -d '\0' < /proc/device-tree/soc@0/isp@acb7000/status 2>&1)"
echo "upstream cci0/cci1 status: $(tr -d '\0' < /proc/device-tree/soc@0/cci@ac15000/status 2>&1) $(tr -d '\0' < /proc/device-tree/soc@0/cci@ac16000/status 2>&1)"
echo "qcom,cam-* node count: $(ls -d /proc/device-tree/soc@0/qcom,* 2>/dev/null | wc -l)"
echo "sensor node (rear OV13858 slot): $(ls -d /proc/device-tree/soc@0/qcom,cci0@ac15000/qcom,cam-sensor* 2>&1 | tr '\n' ' ')"
echo
echo "## packages and firmware file"
rpm -q sp11-camera-spectra 2>&1
ls -l /usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn* /lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn* 2>&1
sha256sum /usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn* 2>&1
echo
echo "## modules (state, refcount, taint)"
for m in camera_x1e80100 qcom_camss i2c_qcom_cci camcc_x1e80100 llcc_qcom qcom_mdt_loader; do
	if [ -d /sys/module/$m ]; then echo "$m: loaded refcnt=$(cat /sys/module/$m/refcnt 2>&1) initstate=$(cat /sys/module/$m/initstate 2>&1) taint=$(cat /sys/module/$m/taint 2>&1)"
	else echo "$m: not loaded"; fi
done
echo "kernel taint: $(cat /proc/sys/kernel/tainted 2>&1)"
echo "modinfo: $(modinfo -F filename camera_x1e80100 2>&1) vermagic=$(modinfo -F vermagic camera_x1e80100 2>&1)"
echo "OF alias qcom,cam-req-mgr (the autoload trigger): $(modinfo -F alias camera_x1e80100 2>/dev/null | grep -c 'qcom,cam-req-mgr') match(es)"
echo "modprobe guard drop-in: $(ls /usr/lib/modprobe.d/sp11-camera-spectra.conf 2>&1)"
echo "lsmod camera|camss|cci: $(lsmod | grep -E 'camera|camss|cci' | tr '\n' ';')"
echo
echo "## platform devices (bound driver per qcom,cam-* device)"
for d in /sys/bus/platform/devices/*qcom,*cam* /sys/bus/platform/devices/*ac13000* /sys/bus/platform/devices/*ac15000* /sys/bus/platform/devices/*acb7000*; do
	[ -e "$d" ] || continue
	echo "$(basename $d): driver=$(basename $(readlink $d/driver 2>/dev/null) 2>/dev/null) status=$(tr -d '\0' < $d/of_node/status 2>/dev/null)"
done | sort -u
echo
echo "## nodes"
ls -l /dev/video* /dev/media* /dev/v4l-subdev* /dev/cam* 2>&1
for d in /sys/class/video4linux/*; do [ -e "$d" ] && echo "$(basename $d): $(cat $d/name 2>&1)"; done
for d in /sys/class/media/*; do [ -e "$d" ] && echo "$(basename $d)"; done 2>/dev/null
command -v v4l2-ctl >/dev/null 2>&1 && v4l2-ctl --list-devices 2>&1 | head -n 40
command -v media-ctl >/dev/null 2>&1 && for m in /dev/media*; do [ -e "$m" ] && { echo "-- media-ctl -p -d $m (first 60 lines)"; timeout 5 media-ctl -p -d "$m" 2>&1 | head -n 60; }; done
echo
echo "## interrupts (camera IRQs: count per CPU, name)"
grep -i -E 'cam|cpas|csid|ife|csiphy|tpg|icp|jpeg|cci|sfe|cdm|bps|ipe' /proc/interrupts 2>&1 | cut -c1-200
echo "total camera-related irq lines: $(grep -c -i -E 'cam|cpas|csid|ife|csiphy|tpg|icp|jpeg|cci|sfe|cdm|bps|ipe' /proc/interrupts)"
echo
echo "## dmesg: Spectra driver (cam_*, CAM_*, camera_x1e80100)"
timeout 8 dmesg --time-format=iso 2>&1 | grep -E 'CAM_|cam_|camera_x1e80100|cam-|CPAS|SMMU.*cam|spectra' | head -n 400 | cut -c1-260
echo
echo "## dmesg: errors and warnings from the camera path"
timeout 8 dmesg --time-format=iso 2>&1 | grep -E 'CAM_ERR|CAM_WARN|cam.*(fail|error|-EINVAL|-ENODEV|-EPROBE_DEFER)|camera_x1e80100.*(fail|error)' | head -n 120 | cut -c1-260
echo
echo "## dmesg: probe results per sub-driver (CAM_INFO probe lines)"
timeout 8 dmesg --time-format=iso 2>&1 | grep -E 'CAM_INFO.*(probe|Probe|PROBE|registered|Registered|Initialized|init)' | head -n 120 | cut -c1-260
echo
echo "## dmesg: CAMERA_ICP firmware load result"
timeout 8 dmesg --time-format=iso 2>&1 | grep -i -E 'CAMERA_ICP|cam_icp|ICP.*(firmware|fw|pas|authent|mbn|elf)|qcom_pas|qcom_scm.*(pas|auth)|firmware.*qcom/x1e80100' | head -n 80 | cut -c1-260
echo "(expected on the TPG-only test: no ICP firmware request at all; a request appears only when a client acquires ICP/IPE/BPS)"
echo
echo "## dmesg: conflicts with the upstream stack and other probe problems"
timeout 8 dmesg --time-format=iso 2>&1 | grep -i -E 'camss|qcom-cci|i2c-qcom-cci|camcc|pinctrl.*(gpio10[0-9]|gpio9[67]|gpio110)|gdsc.*(cam|titan)|iommu.*(cam|fault)|arm-smmu.*(fault|cam)|genpd.*cam|titan' | head -n 80 | cut -c1-260
echo
echo "## power domains, clocks and regulators the driver holds (names only)"
for g in titan ife ipe bps sfe; do grep -i -h "$g" /sys/kernel/debug/pm_genpd/pm_genpd_summary 2>/dev/null | head -n 4; done
[ -r /sys/kernel/debug/pm_genpd/pm_genpd_summary ] || echo "pm_genpd_summary: not readable (debugfs not mounted or not root)"
grep -i -E 'cam_cc|camcc' /sys/kernel/debug/clk/clk_summary 2>/dev/null | head -n 40
[ -r /sys/kernel/debug/clk/clk_summary ] || echo "clk_summary: not readable"
for r in /sys/class/regulator/regulator.*; do n=$(cat $r/name 2>/dev/null); case "$n" in *l1m*|*l5m*|*l6m*|*l16b*) echo "$n: state=$(cat $r/state 2>&1) users=$(cat $r/num_users 2>&1)";; esac; done
echo
echo "## privacy LED and S2 checks (nothing may be lit or driven in the TPG-only test)"
for d in /sys/class/leds/*indicator*; do [ -e "$d" ] && echo "$(basename $d): brightness=$(cat $d/brightness 2>&1) trigger=$(cat $d/trigger 2>&1 | grep -o '\[[^]]*\]')"; done
echo "flash/torch LED class devices (must be none): $(ls -d /sys/class/leds/*flash* /sys/class/leds/*torch* 2>/dev/null | tr '\n' ' ')"
echo "pm8550 flash-led platform device (must have no driver): $(ls -d /sys/bus/platform/devices/*flash* 2>/dev/null | tr '\n' ' ')"
echo
echo "## camera debugfs (names only)"
ls /sys/kernel/debug/camera* 2>&1 | head -n 40
true
