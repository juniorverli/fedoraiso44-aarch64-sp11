# M13 microphone and sound-card checks (audio-speakers test-plan; D26 first test, collection part only).
# Read-only: no mixer write, no playback, no capture started. The speaker first-test PLAYBACK steps are documented in
# image/README.md ("M13 private ISO") and are never run by this script.
echo "## entry"
tr ' ' '\n' </proc/cmdline | grep -E '^sp11\.entry='
echo "dtb model: $(tr '\0' ' ' </sys/firmware/devicetree/base/model 2>&1)"
echo
echo "## /proc/asound/cards"
cat /proc/asound/cards 2>&1
echo
echo "## arecord -l"
timeout 8 arecord -l 2>&1
echo
echo "## aplay -l"
timeout 8 aplay -l 2>&1
echo
echo "## arecord -L (names)"
timeout 8 arecord -L 2>&1 | grep -v '^ ' | head -n 40
echo
echo "## amixer -c 0 contents (read only; D26 first test: PA Volume max 6, PA 0, DAC/COMP switches off)"
timeout 10 amixer -c 0 contents 2>&1 | head -n 400
echo
echo "## D28 UCM files in effect (hashes only)"
( cd /usr/share/alsa/ucm2/Qualcomm/x1e80100 2>/dev/null && sha256sum MICROSOFT-Surface-Pro-11.conf Surface11-*.conf 2>&1 )
echo
echo "## UCM lookup (M14, audio-mics evidence 2026-10-31-m13-mic.md): the card must now list the HiFi verb; list only, nothing is set"
timeout 8 alsaucm -c hw:0 list _verbs 2>&1 | head -n 10
echo
echo "## PCM list (M14: MultiMedia5 capture, index 4, is the V/I trigger front end of the closed-loop topology)"
cat /proc/asound/pcm 2>&1
echo
echo "## speaker guard (read only; first-test entry only gives anything but 'closed')"
timeout 5 cat /sys/kernel/debug/sp11/guard 2>&1 | head -n 40
echo "private speaker files present (names and sizes only): $(ls -l /usr/lib/firmware/qcom/x1e80100/ 2>/dev/null | awk '/sp11c|tplg/{printf "%s(%s) ", $NF, $5}')"
echo
echo "## kernel log: sound stack"
timeout 8 dmesg --time-format=iso 2>&1 | grep -i -E 'q6apm|q6prm|\<apr\>|\<gpr\>|wsa884|soundwire|swr|snd-soc|asoc|audioreach|x1e80100|CMD timeout|microphone|DMIC|va-macro|lpass' | head -n 300
echo
echo "## PipeWire graph (wpctl status as the logged-in user, if a session exists)"
uid=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 != "root" {print $2; exit}')
user=$(loginctl list-sessions --no-legend 2>/dev/null | awk '$3 != "root" {print $3; exit}')
if [ -n "$uid" ] && [ -n "$user" ] && command -v wpctl >/dev/null 2>&1; then
	timeout 15 runuser -u "$user" -- env XDG_RUNTIME_DIR="/run/user/$uid" wpctl status 2>&1 | head -n 80
	echo "== sources (names)"
	timeout 15 runuser -u "$user" -- env XDG_RUNTIME_DIR="/run/user/$uid" wpctl status 2>&1 | sed -n '/Sources:/,/Filters:/p' | head -n 20
else
	echo "(no user session yet, or wpctl missing: wpctl status not run at this snapshot)"
fi
true
