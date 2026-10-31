#!/bin/sh
# Checks the dB to VA_DECn Volume step conversion and the UCM capture-gain default.
# Usage: mic-gain-check.sh [amixer-contents-dump]   (default: the fixture next to this script; a gzip dump is
# accepted, for example the private extra-audio.txt.gz of a device log. Nothing from a dump is printed except
# the two control blocks.)
# Windows endpoint (surface_asdext8380.inf MicArray1): default +14.0 dB, maximum +24.0 dB.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
src=${1:-$here/va-dec-volume.fixture.txt}
ucm=$here/../overlay-audio-routes/usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-MicGain.conf
WIN_DEFAULT_DB=14
WIN_MAX_DB=24

case $src in
*.gz) text=$(gzip -dc "$src") ;;
*) text=$(cat "$src") ;;
esac

fail=0
for n in 0 1; do
	block=$(printf '%s\n' "$text" | awk -v n="VA_DEC$n Volume" '
		index($0, "name=\x27" n "\x27") { f = 1; print; next }
		f && /^numid=/ { exit }
		f { print }')
	[ -n "$block" ] || { echo "FAIL: VA_DEC$n Volume not in $src"; exit 1; }
	# min, max, dBscale-min, step; the TLV is dB = dbmin + step_index * dbstep, step index 0 is mute
	# shellcheck disable=SC2046  # the four numbers are meant to split
	set -- $(printf '%s\n' "$block" | awk '
		match($0, /min=[0-9-]+,max=[0-9]+/) { split(substr($0, RSTART, RLENGTH), a, /[=,]/); mn = a[2]; mx = a[4] }
		match($0, /dBscale-min=-?[0-9.]+dB,step=[0-9.]+dB/) { t = substr($0, RSTART, RLENGTH); gsub(/dBscale-min=|dB|step=/, "", t); split(t, b, ","); dbmin = b[1]; dbstep = b[2] }
		END { print mn, mx, dbmin, dbstep }')
	min=$1 max=$2 dbmin=$3 dbstep=$4
	def=$(awk -v t=$WIN_DEFAULT_DB -v m="$dbmin" -v s="$dbstep" -v mn="$min" 'BEGIN { printf "%d", mn + (t - m) / s + 0.5 }')
	cap=$(awk -v t=$WIN_MAX_DB -v m="$dbmin" -v s="$dbstep" -v mn="$min" 'BEGIN { printf "%d", mn + (t - m) / s + 0.5 }')
	back=$(awk -v v="$def" -v m="$dbmin" -v s="$dbstep" -v mn="$min" 'BEGIN { printf "%.2f", m + (v - mn) * s }')
	echo "VA_DEC$n: min=$min max=$max dBscale-min=$dbmin dB step=$dbstep dB -> +$WIN_DEFAULT_DB dB = step $def (back: $back dB), +$WIN_MAX_DB dB = step $cap"
	[ "$def" -ge "$min" ] && [ "$def" -le "$max" ] || { echo "FAIL: default step out of range"; fail=1; }
	[ "$cap" -ge "$def" ] && [ "$cap" -le "$max" ] || { echo "FAIL: cap step out of range"; fail=1; }
	# the UCM file must write exactly the derived default, and never more than the cap
	set_to=$(awk -v c="VA_DEC$n Volume" 'index($0, "\x27" c "\x27") { print $NF }' "$ucm" | tr -d '"')
	if [ "$set_to" = "$def" ] && [ "$set_to" -le "$cap" ]; then
		echo "PASS: SP11-MicGain.conf writes VA_DEC$n Volume $set_to (= +$WIN_DEFAULT_DB dB, cap step $cap)"
	else
		echo "FAIL: SP11-MicGain.conf writes '$set_to' for VA_DEC$n, expected $def (<= $cap)"
		fail=1
	fi
	# and the old upstream value would have been louder than Windows
	over=$(awk -v v=100 -v m="$dbmin" -v s="$dbstep" -v mn="$min" 'BEGIN { printf "%.0f", m + (v - mn) * s }')
	echo "note: Fedora's DMIC sequences write 100 = $over dB, above the Windows default; our file runs after them"
done
[ "$fail" = 0 ] && echo "ALL PASS" || exit 1
