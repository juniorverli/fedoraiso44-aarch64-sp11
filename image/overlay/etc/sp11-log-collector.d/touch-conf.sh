# M15 touch profile record (image-owned). Read-only. The tap diagnostic (sp11-touch-tap-diag, hardware/touch-pen) is installed as an ON-DEMAND tool and is
# NOT run here: it needs the operator to tap the screen. Run it by hand: sudo /usr/libexec/sp11-touch-tap-diag 30
echo "## iptsd profile of this boot (sp11-touch-conf-select, default B; marker sp11/touch-conf-A selects A)"
cat /run/sp11/touch-conf 2>&1
echo "/etc/iptsd.d: $(ls /etc/iptsd.d 2>&1 | tr '\n' ' ')"
echo "tap diagnostic installed (not run): $( [ -x /usr/libexec/sp11-touch-tap-diag ] && echo yes || echo no )"
echo "iptsd units: $(systemctl list-units 'iptsd@*' --no-legend 2>&1 | awk '{print $1":"$3}' | tr '\n' ' ')"
true
