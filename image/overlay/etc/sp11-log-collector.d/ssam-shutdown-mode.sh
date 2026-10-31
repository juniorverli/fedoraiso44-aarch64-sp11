# M13 (ec-sam evidence 2026-10-30-windows-transition.md sections 5-6): which surface_aggregator.shutdown_mode this boot used.
# Read-only. The mode only acts at the next poweroff; this record says what was requested at boot and what the module holds.
echo "## cmdline"
tr ' ' '\n' </proc/cmdline | grep -E '^(surface_aggregator\.|sp11\.entry=|sp11\.ssam_)' || echo "(no surface_aggregator or sp11.ssam_* argument)"
echo
echo "## module parameter (sysfs)"
f=/sys/module/surface_aggregator/parameters/shutdown_mode
if [ -r "$f" ]; then echo "shutdown_mode=$(timeout 3 cat "$f" 2>&1)"; else echo "(absent: $f; the module is not loaded or has no parameter)"; fi
echo
echo "## kernel log: shutdown mode"
timeout 8 dmesg 2>&1 | grep -i -E 'shutdown mode|ssam.*shutdown|surface_aggregator.*shutdown' | head -n 20
echo
echo "## module info (parameter description only)"
timeout 8 modinfo -F parm surface_aggregator 2>&1 | grep -i shutdown_mode
true
