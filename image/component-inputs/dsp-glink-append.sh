
# ---- image worker append (M10): sp11-glink diagnostic (R-K1) and remoteproc state ----
# Appended to the owner's collector by scripts/image-build-kiwi.sh. Commands are the owner's exact list
# (hardware/dsp-subsystems/evidence/2026-10-29-rea-windows.md section 7.4). Read only.
echo
echo "## sp11-glink: dmesg | grep sp11-glink"
timeout 8 dmesg 2>&1 | grep sp11-glink | head -n 2000
echo
echo "## sp11-glink: journalctl -k -b | grep sp11-glink"
timeout 20 journalctl -k -b --no-pager 2>&1 | grep sp11-glink | head -n 2000
echo
echo "## sp11-glink: OPEN_ACK wait timed out"
timeout 8 dmesg 2>&1 | grep 'sp11-glink: OPEN_ACK wait timed out'
echo
echo "## sp11-glink: OPEN and OPEN_ACK of IPCRTR and FASTRPCGLINK"
timeout 8 dmesg 2>&1 | grep -E 'sp11-glink: (tx|rx) OPEN(_ACK)? name=(IPCRTR|FASTRPCGLINK)'
echo
echo "## sp11-glink: create_ept failures"
timeout 8 dmesg 2>&1 | grep -E 'sp11-glink: create_ept .* failed'
echo
echo "## sp11-glink: counts (sp11-glink lines, callbacks suppressed)"
echo "sp11-glink lines: $(timeout 8 dmesg 2>&1 | grep -c 'sp11-glink:')"
echo "callbacks suppressed: $(timeout 8 dmesg 2>&1 | grep -c 'callbacks suppressed')"
echo
echo "## remoteproc state after the GLINK lines: name state"
for r in /sys/class/remoteproc/remoteproc*; do
	[ -d "$r" ] || continue
	echo "$(basename "$r"): name=$(R "$r/name") state=$(R "$r/state")"
done
true
