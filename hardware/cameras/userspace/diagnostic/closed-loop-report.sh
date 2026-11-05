#!/bin/bash
# One-command muted closed-loop diagnostic for the `safe, muted closed-loop VI` entry.
#
# It refuses to run anywhere else: the kernel command line must carry
# sp11.nospk=1 (the kill switch stays on). It never opens playback, never
# unmutes, never changes a control and never reads capture samples.
#
#   * checks the three private CL firmware files are installed (hashes only);
#   * finds the MultiMedia5 capture PCM and records its info/status/hw_params;
#   * runs the speaker supervisor for five seconds (capture only, frames are
#     forwarded, not read) and records the exit status;
#   * records the guard report and the kernel/journal lines that name the
#     audio path.
#
# Output is a 0600 text file (default /var/tmp/sp11-cl-report.txt) plus the
# same lines on the terminal. A non-124 supervisor exit, a lost RUNNING state,
# an XRUN or a missing guard field is a stop/incomplete result, not a pass.

set -uo pipefail

OUT=${SP11_CL_REPORT_OUT:-/var/tmp/sp11-cl-report.txt}
GUARD=${SP11_CL_REPORT_GUARD:-/usr/libexec/sp11/guard-report}
SUP=${SP11_CL_REPORT_SUPERVISOR:-/usr/libexec/sp11/speaker-supervisor}
ASOUND=${SP11_CL_ASOUND_ROOT:-/proc/asound}
FWDIR=${SP11_CL_FW_DIR:-/usr/lib/firmware/qcom/x1e80100}
MODEL=X1E80100-Microsoft-Surface-Pro-11-CL
HOLD_SECONDS=${SP11_CL_HOLD_SECONDS:-5}

die() { echo "cl-report: $*" >&2; exit 1; }

if [ "${SP11_CL_REPORT_TEST:-0}" != 1 ]; then
	case " $(cat /proc/cmdline) " in
		*' sp11.nospk=1 '*) ;;
		*) die "not the muted closed-loop entry (sp11.nospk=1 required)" ;;
	esac
	[ -t 0 ] || die "an interactive terminal and an operator are required"
	cat <<'EOF'
This is the MUTED closed-loop diagnostic. Nothing is played, unmuted or
changed. The supervisor only starts the MultiMedia5 capture and forwards its
frames. The speaker kill switch (sp11.nospk) stays in force. An operator must
be present; stop on any fault, XRUN or unexpected exit.
EOF
	read -r answer || die "no answer"
	[ "$answer" = OBSERVING ] || die "cancelled"
fi

for f in "$FWDIR/$MODEL-tplg.bin" "$FWDIR/$MODEL-sp11cl.bin" "$FWDIR/$MODEL-sp11cal.bin"; do
	[ -f "$f" ] || die "missing private CL file $(basename "$f")"
done

cap_card= cap_pcm=
for info in "$ASOUND"/card*/pcm*c/info; do
	[ -r "$info" ] || continue
	if grep -q 'MultiMedia5' "$info"; then
		card_dir=$(dirname "$(dirname "$info")")
		pcm_dir=$(dirname "$info")
		cap_card=${card_dir##*/card}
		cap_pcm=${pcm_dir##*/pcm}
		cap_pcm=${cap_pcm%c}
		break
	fi
done
[ -n "$cap_card" ] && [ -n "$cap_pcm" ] || die "no MultiMedia5 capture PCM under $ASOUND"
hw="hw:$cap_card,$cap_pcm"

tmp=$(mktemp /tmp/cl-report.XXXXXX)
exec 3>"$OUT"
chmod 0600 "$OUT" 2>/dev/null || true

say() { printf '%s\n' "$*" | tee -a "$OUT" >&2; }

say "== Muted closed-loop report $(date -u +%Y-%m-%dT%H:%M:%SZ)"
say "-- private CL files under $FWDIR"
for f in "$FWDIR/$MODEL-tplg.bin" "$FWDIR/$MODEL-sp11cl.bin" "$FWDIR/$MODEL-sp11cal.bin"; do
	say "   $(basename "$f") sha256 $(sha256sum "$f" | cut -d' ' -f1)"
done

say "-- MultiMedia5 capture $hw"
if [ -r "$ASOUND/card$cap_card/pcm${cap_pcm}c/info" ]; then
	say "   info: $(grep -E '^(name|id):' "$ASOUND/card$cap_card/pcm${cap_pcm}c/info" | tr '\n' ' ')"
fi

say "-- guard report before"
"$GUARD" >>"$OUT" 2>&1 || say "   guard-report exit $?"

status_before=$(cat "$ASOUND/card$cap_card/pcm${cap_pcm}c/sub0/status" 2>/dev/null || true)
say "-- PCM status before: ${status_before:-unreadable}"

timeout --signal=TERM --kill-after=2s "${HOLD_SECONDS}s" "$SUP" "$hw" >"$tmp" 2>&1
sup_rc=$?
sed 's/^/   supervisor: /' "$tmp" | tee -a "$OUT" >&2

status_after=$(cat "$ASOUND/card$cap_card/pcm${cap_pcm}c/sub0/status" 2>/dev/null || true)
say "-- PCM status after: ${status_after:-unreadable}"
if [ -r "$ASOUND/card$cap_card/pcm${cap_pcm}c/sub0/hw_params" ]; then
	say "   hw_params: $(grep -v '^closed' "$ASOUND/card$cap_card/pcm${cap_pcm}c/sub0/hw_params" | tr '\n' ' ')"
fi

say "-- guard report after"
"$GUARD" >>"$OUT" 2>&1 || say "   guard-report exit $?"

say "-- journal lines"
journalctl -k -b --no-pager 2>/dev/null |
	grep -iE 'sp11|audioreach|q6apm|MultiMedia5' | tail -40 |
	sed 's/^/   /' | tee -a "$OUT" >&2

case $sup_rc in
	124) say "RESULT: supervisor held the capture for ${HOLD_SECONDS}s (timeout 124); inspect the guard fields, no sound was produced" ;;
	0)   say "RESULT: supervisor exited 0 on SIGTERM; inspect the log above" ;;
	*)   say "RESULT: supervisor exited $sup_rc before the hold ended (stop/incomplete)" ;;
esac
rm -f "$tmp"
echo "report $OUT (mode 0600)" >&2
[ "$sup_rc" = 124 ] && exit 0
exit 1
