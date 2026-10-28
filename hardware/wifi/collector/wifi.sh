# SP11 log collector drop-in for the wifi component.
# Install as /etc/sp11-log-collector.d/wifi.sh (sourced by sp11-log-collector in a subshell,
# output goes to extra-wifi.txt). Owner: wifi worker; installed by the image worker.
#
# Read-only, except one thing: `iw dev <if> scan` sends probe requests. It runs once per boot
# (stamp in /run) and only COUNTS the BSSs per band; no SSID or BSSID is stored.
# Privacy (S5): no MAC address, no serial. Every MAC-shaped string is masked by mask(); for the
# station address only a hash prefix is printed (compare with hardware/wifi/tools/check-mac.sh).
# The core collector's lspci.txt still carries the endpoint's Device Serial Number line.
# Never paste lspci.txt or journal.txt into git.

mask() { sed -E 's/([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}/<MAC>/g; s/(Device Serial Number ).*/\1<DSN>/'; }
run() { echo "### $*"; timeout 20 "$@" 2>&1 | mask; echo; }
sh_() { echo "### $1"; timeout 20 bash -c "$1" 2>&1 | mask; echo; }

echo "== state at uptime $(cut -d' ' -f1 /proc/uptime) s, boot entry $(tr ' ' '\n' </proc/cmdline | grep '^sp11.entry=')"

echo "== 1 modules and parameters"
sh_ "lsmod | grep -E 'ath12k|pci_pwrctrl|pwrseq|phy_qcom_qmp_pcie|qrtr|mhi|qmi_helpers|cfg80211|mac80211|rfkill|btqca|hci_uart'"
sh_ "for p in /sys/module/ath12k/parameters/*; do echo \"\$p=\$(cat \$p)\"; done"
sh_ "grep -E 'CONFIG_ATH12K' /proc/config.gz 2>/dev/null; zcat /proc/config.gz 2>/dev/null | grep -E '^CONFIG_ATH12K'"

echo "== 2 dependency chain: pcie4 controller, phy, pwrctrl, pwrseq"
sh_ "ls -l /sys/bus/platform/devices/1c08000.pcie/ /sys/bus/platform/devices/1c0e000.phy/ 2>&1 | grep -E 'driver|supplier|consumer|waiting|power_state'"
sh_ "for d in /sys/bus/platform/devices/1c08000.pcie /sys/bus/platform/devices/1c0e000.phy /sys/bus/platform/devices/wcn7850-pmu /sys/bus/platform/devices/*wifi*; do [ -e \$d ] && echo \"\$d driver=\$(basename \$(readlink \$d/driver 2>/dev/null) 2>/dev/null) waiting_for_supplier=\$(cat \$d/waiting_for_supplier 2>/dev/null)\"; done"
sh_ "ls -l /sys/bus/platform/drivers/pci-pwrctrl-pwrseq/ /sys/bus/platform/drivers/pwrseq-qcom_wcn/ 2>&1 | grep -v -E '^total|module|bind|uevent'"
sh_ "ls /sys/class/pwrseq/ 2>&1"
sh_ "grep -E 'pcie|pwrctrl|pwrseq|wcn|wifi|1c08000|1c0e000' /sys/kernel/debug/devices_deferred"

echo "== 3 PCIe link and endpoint"
run lspci -nnk -d 17cb:
run lspci -tv
sh_ "for d in /sys/bus/pci/devices/0004:*; do echo \"\$(basename \$d) vendor=\$(cat \$d/vendor) device=\$(cat \$d/device) subsys=\$(cat \$d/subsystem_vendor 2>/dev/null):\$(cat \$d/subsystem_device 2>/dev/null) speed=\$(cat \$d/current_link_speed 2>/dev/null) max=\$(cat \$d/max_link_speed 2>/dev/null) width=\$(cat \$d/current_link_width 2>/dev/null)/\$(cat \$d/max_link_width 2>/dev/null) runtime=\$(cat \$d/power/runtime_status 2>/dev/null) d3cold=\$(cat \$d/d3cold_allowed 2>/dev/null) driver=\$(basename \$(readlink \$d/driver 2>/dev/null) 2>/dev/null)\"; done"
sh_ "lspci -vv -s 0004:00:00.0 | grep -E 'LnkCap|LnkSta|LnkCtl|DevSta|AER|UESta|CESta|Slot|Wake'"
sh_ "lspci -vv -s 0004:01:00.0 | grep -E 'Region|LnkCap|LnkSta|LnkCtl|DevSta|UESta|CESta|L1SubCtl|Kernel driver|MSI:'"
sh_ "for f in /sys/bus/pci/devices/0004:*/aer_dev_correctable /sys/bus/pci/devices/0004:*/aer_dev_nonfatal /sys/bus/pci/devices/0004:*/aer_dev_fatal; do [ -r \$f ] && { echo \"== \$f\"; cat \$f; }; done"

echo "== 4 GPIO, pinctrl, regulators (WCN rails, PERST, WAKE, CLKREQ)"
sh_ "grep -E ' gpio-(116|117|146|147|148|214) ' /sys/kernel/debug/gpio"
sh_ "grep -E '^pin (116|117|146|147|148|214) ' /sys/kernel/debug/pinctrl/*/pinmux-pins"
sh_ "grep -i -E 'wcn|pmu|l3i_0p8|l3e_1p2|l15b' /sys/kernel/debug/regulator/regulator_summary"
sh_ "for n in /sys/class/regulator/regulator.*/name; do d=\$(dirname \$n); case \$(cat \$n) in VREG_WCN*|vreg_pmu*|vreg_l3i*|vreg_l3e*|vreg_l15b*) echo \"\$(cat \$n) state=\$(cat \$d/state) microvolts=\$(cat \$d/microvolts 2>/dev/null) use=\$(cat \$d/num_users)\";; esac; done"
sh_ "grep -E 'pcie_4|pcie4' /sys/kernel/debug/pm_genpd/pm_genpd_summary"
sh_ "grep -E 'gcc_pcie_4|tcsr_pcie_2l_4|pcie4' /sys/kernel/debug/clk/clk_summary"

echo "== 5 ath12k messages (kernel log)"
sh_ "dmesg | grep -i -E 'ath12k|pwrctrl|pwrseq|wcn7850|qrtr|mhi mhi|1c08000|0004:|cfg80211|regulatory|rfkill|pcie.*link|wlan|board|regdb|firmware' | grep -v -E 'systemd|audit' | tail -150"
sh_ "dmesg | grep -i -E 'ath12k.*(fail|error|timeout|unable|invalid|can.t|crash|firmware|board|regdb|rfkill|m3|amss)|Direct firmware load.*(ath12k|qca)|mhi.*(error|timeout|fail)'"

echo "== 6 firmware files seen by the kernel (names, sizes, hashes of public blobs only)"
sh_ "ls -l /usr/lib/firmware/ath12k/WCN7850/hw2.0/ /usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/ 2>&1"
sh_ "sha256sum /usr/lib/firmware/ath12k/WCN7850/hw2.0/*.xz /usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/* 2>/dev/null"
sh_ "rpm -q atheros-firmware linux-firmware qcom-firmware wireless-regdb"
sh_ "ls /sys/firmware/dmi/entries 2>/dev/null | grep -E '^248-' ; dmidecode -t 248 2>&1 | head -20"

echo "== 7 netdev, rfkill, NetworkManager, regulatory"
run rfkill list
run rfkill --output ID,TYPE,DEVICE,SOFT,HARD --noheadings
sh_ "for r in /sys/class/rfkill/rfkill*; do echo \"\$(basename \$r) name=\$(cat \$r/name) type=\$(cat \$r/type) soft=\$(cat \$r/soft) hard=\$(cat \$r/hard) state=\$(cat \$r/state) persistent=\$(cat \$r/persistent)\"; done"
run iw dev
run iw reg get
sh_ "iw phy | grep -E 'Wiphy|Band|Frequencies|\\* [0-9]+ MHz|Supported interface modes|HE Iftypes|EHT Iftypes|max # scan SSIDs' | head -60"
sh_ "iw phy | grep -c -E '\\* 6[0-9]{3} MHz'"
sh_ "for i in \$(ls /sys/class/ieee80211/*/device/net 2>/dev/null); do echo \"\$i operstate=\$(cat /sys/class/net/\$i/operstate) flags=\$(cat /sys/class/net/\$i/flags) addr_assign_type=\$(cat /sys/class/net/\$i/addr_assign_type)\"; a=\$(cat /sys/class/net/\$i/address); echo \"\$i mac_sha256_16=\$(printf '%s' \"\$a\" | tr 'A-F' 'a-f' | sha256sum | cut -c1-16) mac_first_octet=\$(printf '%s' \"\${a%%:*}\")-bits(locally_administered=\$(( 0x\${a%%:*} >> 1 & 1 )) multicast=\$(( 0x\${a%%:*} & 1 )))\"; done"
sh_ "for i in \$(ls /sys/class/ieee80211/*/device/net 2>/dev/null); do ethtool -i \$i; done"
run nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev
run nmcli radio
run nmcli -t -f WIFI-HW,WIFI,WWAN-HW,WWAN general
sh_ "journalctl -b --no-pager -u NetworkManager -u wpa_supplicant -o short-monotonic | grep -i -E 'wlP|wlan|wifi|rfkill|killswitch|supplicant|scan|regdom|country|state change|unavailable' | tail -60"
sh_ "ip -br link | grep -v -E '^lo '"
sh_ "ip -br addr | grep -E '^wl'"

echo "== 8 scan count, once per boot (probe requests are sent; counts only)"
if [ ! -e /run/sp11-wifi-scan.done ] && [ "$(cut -d. -f1 /proc/uptime)" -ge 60 ]; then
	touch /run/sp11-wifi-scan.done
	for i in $(ls /sys/class/ieee80211/*/device/net 2>/dev/null); do
		echo "### iw dev $i scan (counts per band)"
		timeout 25 iw dev "$i" scan 2>&1 | awk '
			/^BSS /{n++}
			/^\tfreq:/{f=int($2); if (f<3000) b24++; else if (f<5900) b5++; else b6++}
			/command failed|Operation not|Network is down|busy/{print "iw error: " $0}
			END{printf "bss_total=%d bss_2g4=%d bss_5g=%d bss_6g=%d\n", n, b24, b5, b6}'
	done
else
	echo "skipped: already done in this boot, or uptime < 60 s"
fi
