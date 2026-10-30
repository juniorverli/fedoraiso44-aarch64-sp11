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
# M9 (usb-typec README R-I1, reference-port evidence, test-plan F): read-only; no retimer register read, no debugfs write.
shsnap usb-typec-bindings.txt 'for d in /sys/bus/i2c/devices/*-0008 /sys/bus/auxiliary/devices/pmic_glink.*; do [ -d "$d" ] || continue; printf "%s driver=" "${d##*/}"; if [ -L "$d/driver" ]; then readlink "$d/driver"; else printf "unbound\n"; fi; done'
shsnap usb-typec-config.txt 'zcat /proc/config.gz 2>&1 | grep -E "CONFIG_(TYPEC_MUX_PS883X|TYPEC_UCSI|UCSI_PMIC_GLINK|QCOM_PMIC_GLINK|DRM_AUX_HPD_BRIDGE|PHY_QCOM_QMP_COMBO|PHY_QCOM_EUSB2_REPEATER|USB_DWC3_QCOM|USB_XHCI_PLATFORM|DEBUG_INFO_BTF)="'
shsnap usb-typec-partner.txt 'for p in /sys/class/typec/port*; do [ -d "$p" ] || continue; echo "== $p"; for f in data_role power_role orientation usb_capability power_operation_mode; do [ -r "$p/$f" ] && echo "$f=$(cat $p/$f 2>&1)"; done; done; for p in /sys/class/typec/port*-partner; do [ -d "$p" ] || continue; echo "== $p"; for f in accessory_mode supports_usb_power_delivery; do [ -r "$p/$f" ] && echo "$f=$(cat $p/$f 2>&1)"; done; done'
shsnap usb-lsusb-tree.txt 'lsusb -t 2>&1'
