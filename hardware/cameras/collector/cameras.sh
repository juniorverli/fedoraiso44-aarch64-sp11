# SP11 log collector drop-in for the cameras component.
# Install as /etc/sp11-log-collector.d/cameras.sh (sourced by sp11-log-collector in a subshell,
# output goes to extra-cameras.txt). Owner: cameras worker; installed by the image worker.
#
# READ-ONLY. It reads sysfs, debugfs, the kernel log and the media/V4L2 graph. It does not stream,
# does not write a register, does not run i2cdetect or any I2C transfer by hand (the CCI buses carry
# an EEPROM and a lens actuator), does not touch an LED, a GPIO, the PMIC flash or the IR emitter
# (risk S2). `cam -l` and `media-ctl -p` only enumerate; no stream is started.
# Privacy (S5): the register blobs are reported by name, size and a SHA-256 prefix, never by content.

run() { echo "### $*"; timeout 25 "$@" 2>&1; echo; }
sh_() { echo "### $1"; timeout 25 bash -c "$1" 2>&1; echo; }

echo "== state at uptime $(cut -d' ' -f1 /proc/uptime) s, boot entry $(tr ' ' '\n' </proc/cmdline | grep '^sp11.entry=')"

echo "== 1 kernel configuration and modules"
sh_ "zcat /proc/config.gz 2>/dev/null | grep -E '^(# )?CONFIG_(VIDEO_QCOM_CAMSS|I2C_QCOM_CCI|VIDEO_OV13858|VIDEO_IMX681|VIDEO_VD55G1|LEDS_GPIO|V4L2_CCI_I2C|CRC32|DMABUF_HEAPS|DMABUF_HEAPS_SYSTEM|CLK_X1E80100_CAMCC|REGULATOR_QCOM_RPMH)[= ]'"
sh_ "lsmod | grep -E 'qcom_camss|i2c_qcom_cci|ov13858|imx681|vd55g1|videodev|v4l2_fwnode|v4l2_cci|leds_gpio|camcc'"

echo "== 2 kernel log"
sh_ "dmesg | grep -i -E 'camss|cci|csiphy|csid|camcc|ov13858|imx681|vd55g|v4l2|register blob|firmware.*(ov13858|imx681)|privacy|indicator|v4l2-async|video[0-9]' | tail -150"
sh_ "dmesg | grep -i -E 'probe of .* failed|deferred|-EPROBE_DEFER|devices_deferred' | tail -30"
sh_ "cat /sys/kernel/debug/devices_deferred 2>/dev/null"

echo "== 3 register blobs (name, size, SHA-256 prefix only)"
sh_ "for f in /usr/lib/firmware/updates/ov13858-mshw0491.bin /usr/lib/firmware/updates/imx681-mshw0490.bin /usr/lib/firmware/updates/vd55g0-mshw0492.bin /usr/lib/firmware/ov13858-mshw0491.bin /usr/lib/firmware/imx681-mshw0490.bin; do if [ -e \$f ]; then echo \"\$f \$(stat -c %s \$f) bytes sha256=\$(sha256sum \$f | cut -c1-16)\"; else echo \"\$f absent\"; fi; done"

echo "== 4 I2C devices as the kernel bound them (no bus scan)"
sh_ "for d in /sys/bus/i2c/devices/*; do n=\$(cat \$d/name 2>/dev/null); case \"\$n\" in *ov13858*|*imx681*|*vd55g*|*dw98*|*24c*|*eeprom*) echo \"\$d name=\$n driver=\$(basename \$(readlink \$d/driver 2>/dev/null) 2>/dev/null) of_node=\$(readlink \$d/of_node 2>/dev/null)\";; esac; done"
sh_ "ls -l /sys/bus/i2c/drivers/ov13858 /sys/bus/i2c/drivers/imx681 2>&1 | grep -v '^total'"
sh_ "for d in /sys/bus/platform/devices/ac15000.cci /sys/bus/platform/devices/ac16000.cci /sys/bus/platform/devices/acb7000.isp; do [ -e \$d ] && echo \"\$d driver=\$(basename \$(readlink \$d/driver 2>/dev/null) 2>/dev/null) waiting_for_supplier=\$(cat \$d/waiting_for_supplier 2>/dev/null)\" || echo \"\$d absent\"; done"

echo "== 5 media graph and V4L2 devices (enumeration only)"
sh_ "ls -l /dev/media* /dev/video* /dev/v4l-subdev* /dev/dma_heap 2>&1"
run v4l2-ctl --list-devices
for m in /dev/media*; do [ -e "$m" ] && run media-ctl -d "$m" -p; done
sh_ "for sd in /dev/v4l-subdev*; do echo \"-- \$sd: \$(v4l2-ctl -d \$sd --info 2>&1 | grep -E 'Driver name|Card type' | tr '\n' ' ')\"; v4l2-ctl -d \$sd --list-subdev-mbus-codes 0 2>&1 | head -6; done"
sh_ "for sd in /dev/v4l-subdev*; do n=\$(v4l2-ctl -d \$sd --info 2>&1 | grep 'Card type'); case \"\$n\" in *ov13858*|*imx681*) echo \"-- controls of \$sd\"; v4l2-ctl -d \$sd -l 2>&1 | head -25;; esac; done"

echo "== 6 libcamera (enumeration only, no capture)"
run cam -l
sh_ "LIBCAMERA_LOG_LEVELS='*:INFO' cam -l 2>&1 | grep -i -E 'camera|sensor|pipeline|simple|softisp|helper|tuning|ipa' | head -40"
sh_ "rpm -q libcamera libcamera-ipa libcamera-tools pipewire-plugin-libcamera snapshot v4l-utils 2>&1"

echo "== 7 privacy indicators (read the LED class state only)"
sh_ "for l in /sys/class/leds/*indicator*; do [ -e \$l ] && echo \"\$l brightness=\$(cat \$l/brightness) max=\$(cat \$l/max_brightness) trigger=\$(cat \$l/trigger 2>/dev/null | tr ' ' '\n' | grep '\[' )\"; done"

echo "== 8 GPIO, pins, regulators and clocks (debugfs, read-only)"
sh_ "grep -E 'gpio-(96|97|100|101|102|103|104|105|109|110|225|235|236|237) ' /sys/kernel/debug/gpio"
sh_ "grep -E 'pin (96|97|100|101|102|103|104|105|109|110|225|235|236|237) ' /sys/kernel/debug/pinctrl/*tlmm*/pinmux-pins 2>/dev/null"
sh_ "grep -E 'vreg_l(7b|16b|[1-7]m|1c|2c|2j|3j)' /sys/kernel/debug/regulator/regulator_summary"
sh_ "grep -i -E 'cam_cc_(mclk[0-4]|cci_[01]|csiphy[0-4]|csi[0-4]phytimer|cpas_ahb|titan)' /sys/kernel/debug/clk/clk_summary | head -30"
sh_ "for r in /sys/class/regulator/regulator.*; do n=\$(cat \$r/name 2>/dev/null); case \$n in vreg_l7b*|vreg_l16b*|vreg_l[1-7]m*) echo \"\$n state=\$(cat \$r/state 2>/dev/null) uV=\$(cat \$r/microvolts 2>/dev/null) users=\$(cat \$r/num_users 2>/dev/null)\";; esac; done"
