# M13 (cameras test-plan.md "Collector"): rear OV13858 diagnostic. Read-only: no i2cdetect (the CCI buses carry an EEPROM and a
# lens actuator), no media-ctl link change, no stream, no IR emitter or flash (S2). Debugfs files only through the allow-list.
echo "## entry and DTB"
tr ' ' '\n' </proc/cmdline | grep -E '^sp11\.entry='
echo "dtb model: $(tr '\0' ' ' </sys/firmware/devicetree/base/model 2>&1)"
echo
echo "## dmesg: camera stack"
timeout 8 dmesg --time-format=iso 2>&1 | grep -i -E 'camss|cci|csiphy|camcc|ov13858|v4l2|media|privacy|led' | head -n 300
echo
echo "## i2c devices (names)"
ls /sys/bus/i2c/devices 2>&1
for d in /sys/bus/i2c/devices/*; do [ -r "$d/name" ] && echo "$(basename "$d"): $(cat "$d/name" 2>&1) driver=$(basename "$(readlink -e "$d/driver" 2>/dev/null)" 2>/dev/null)"; done | grep -i -E 'ov|cci|cam' || true
echo
echo "## device nodes"
ls -l /dev/media* /dev/video* /dev/v4l-subdev* 2>&1
echo
echo "## media graph (media-ctl -p, listing only)"
if command -v media-ctl >/dev/null 2>&1; then
	for m in /dev/media*; do [ -e "$m" ] || continue; echo "== $m"; timeout 10 media-ctl -d "$m" -p 2>&1 | head -n 120; done
else
	echo "media-ctl: not installed"
fi
echo
echo "## leds"
ls /sys/class/leds 2>&1 | grep -i -E 'indicator|camera' || echo "(no camera or indicator LED)"
echo
echo "## gpio (97 103 104 105 110 225)"
dbgcat /sys/kernel/debug/gpio | grep -E 'gpio(97|103|104|105|110|225) ' || echo "(none matched)"
echo
echo "## regulators (l1m l5m l6m l1c l2c)"
dbgcat /sys/kernel/debug/regulator/regulator_summary | grep -i -E 'l[156]m|l[12]c' || echo "(none matched)"
echo
echo "## clocks (cam_cc_mclk1, cam_cc_cci_0, cam_cc_csiphy1)"
dbgcat /sys/kernel/debug/clk/clk_summary | grep -i -E 'cam_cc_mclk1|cam_cc_cci_0|cam_cc_csiphy1' || echo "(none matched)"
echo
echo "## libcamera (listing only, no capture)"
if command -v cam >/dev/null 2>&1; then timeout 20 cam -l 2>&1 | head -n 40; else echo "cam: not installed"; fi
echo
echo "## camera modules loaded"
grep -E '^(ov13858|qcom_camss|qcom-camss|i2c_qcom_cci|camcc_x1e80100|leds_gpio|videobuf2_[a-z_0-9]+|v4l2_[a-z_0-9]+) ' /proc/modules 2>&1
true
