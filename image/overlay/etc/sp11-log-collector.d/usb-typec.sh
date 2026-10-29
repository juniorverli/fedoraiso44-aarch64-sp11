# usb-typec test-plan section B; read-only. Debugfs reads use the collector allow-list.
attrs typec.txt        /sys/class/typec/*
attrs usb_role.txt     /sys/class/usb_role/*
shsnap typec-tree.txt  'ls -lR /sys/class/typec 2>&1'
shsnap usb-speed.txt   'for d in /sys/bus/usb/devices/*; do [ -r "$d/speed" ] && echo "$(basename $d) speed=$(cat $d/speed) ver=$(cat $d/version 2>&1) product=$(cat $d/product 2>&1)"; done'
shsnap xhci-ports.txt  'for f in /sys/kernel/debug/usb/xhci/*/ports/port*/portsc; do echo "== $f"; dbgcat "$f"; done'
shsnap usb-devices.txt 'dbgcat /sys/kernel/debug/usb/devices | grep -v -i "^S:  SerialNumber"'
shsnap usb-drivers.txt 'ls -l /sys/bus/platform/drivers/dwc3-qcom /sys/bus/auxiliary/devices /sys/bus/auxiliary/drivers /sys/bus/rpmsg/devices /sys/bus/i2c/devices 2>&1'
shsnap usb-dmesg.txt   'dmesg --time-format=iso 2>&1 | grep -i -E "dwc3|xhci|ps883x|ucsi|pmic_glink|pmic-glink|altmode|qmp|eusb2|repeater|typec|pdr|charger_pd|battmgr|usb [0-9]|usb[0-9]|device link|dependency cycle" | grep -v -i serialnumber'
shsnap usb-regs.txt    'grep -E "rtmr|RTMR|l15b|l1i_|l1d_|l1j|l2j|l3j|l2b|l14b|l8b|l2d|l3d" /sys/kernel/debug/regulator/regulator_summary 2>&1; grep -E "gpio(121|123|170|175|176|186|188) " /sys/kernel/debug/gpio 2>&1'
shsnap charge.txt      'upower -d 2>&1 | grep -v -i -E "serial|model|vendor"'
