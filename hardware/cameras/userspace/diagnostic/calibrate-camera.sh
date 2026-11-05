#!/bin/bash
# Guided measured white-balance calibration for both RGB cameras.
#
# For each sensor it captures a capped-lens dark frame and a neutral (white
# sheet) frame with the existing camera diagnostic, picks the packed RAW10
# file by its exact size, and installs the measured gains with calibrate.py.
# Nothing is played or unmuted; the camera streams are normal captures and the
# privacy indicator must be watched. The tuning backup is `.sp11-orig`;
# `calibrate.py --restore` undoes it.
#
# Usage: calibrate-camera.sh [front|rear|both]   (default both)
# Environment overrides exist only for host tests: SP11_CAL_CAPTURE,
# SP11_CAL_TOOL, SP11_CAL_ROOT, SP11_CAL_ROOTDIR, SP11_CAL_TEST.

set -uo pipefail

CAPTURE=${SP11_CAL_CAPTURE:-/usr/libexec/sp11/camera-diagnostic/capture.py}
TOOL=${SP11_CAL_TOOL:-/usr/libexec/sp11/camera-diagnostic/calibrate.py}
OUTROOT=${SP11_CAL_ROOTDIR:-/var/tmp}
WHICH=${1:-both}

die() { echo "calibrate-camera: $*" >&2; exit 1; }

case $WHICH in
	front|rear|both) ;;
	*) die "usage: $0 [front|rear|both]" ;;
esac

if [ "${SP11_CAL_TEST:-0}" != 1 ]; then
	case " $(cat /proc/cmdline) " in
		*' sp11.entry=safe '*) ;;
		*) die "not the safe entry (sp11.entry=safe required)" ;;
	esac
	[ -t 0 ] || die "an interactive terminal and an observer are required"
	cat <<'EOF'
Close every camera client. The privacy indicator turns on while each capture
runs; a person must watch it and stop on a dark indicator, a fault or a reset.
No LED, flash, control or exposure override is used. Files stay under /var/tmp.
EOF
	read -r answer || die "no answer"
	[ "$answer" = OBSERVING ] || die "cancelled"
fi

# front|rear -> sensor name width height stride cfa
spec() {
	case $1 in
		front) echo "imx681 3840 2160 4800 RGGB" ;;
		rear)  echo "ov13858 2112 1188 2640 GRBG" ;;
		*) return 1 ;;
	esac
}

pick_raw() { # dir, expected size
	local dir=$1 want=$2 f best=
	for f in "$dir"/*.bin; do
		[ -f "$f" ] || continue
		[ "$(stat -c %s "$f")" = "$want" ] || continue
		best=$f
	done
	printf '%s\n' "$best"
}

run_sensor() {
	local which=$1
	read -r sensor width height stride cfa < <(spec "$which")
	local dark="$OUTROOT/cal-$which-dark" neutral="$OUTROOT/cal-$which-neutral"
	[ ! -e "$dark" ] || die "$dark already exists; move it away first"
	[ ! -e "$neutral" ] || die "$neutral already exists; move it away first"

	echo
	echo "== $which ($sensor): cover the lens completely with a black cloth."
	echo "   Keep the privacy indicator visible; press Enter only when covered."
	read -r _ || die "no answer"
	"$CAPTURE" --sensor "$sensor" --target dark --frames 2 --out "$dark" ||
		die "dark capture failed for $sensor"

	echo
	echo "== $sensor: now fill the centre with a white sheet, evenly lit, no clipping."
	echo "   Press Enter only when ready."
	read -r _ || die "no answer"
	"$CAPTURE" --sensor "$sensor" --target neutral --frames 2 --out "$neutral" ||
		die "neutral capture failed for $sensor"

	local dark_raw neutral_raw want
	want=$((stride * height))
	dark_raw=$(pick_raw "$dark" "$want")
	neutral_raw=$(pick_raw "$neutral" "$want")
	[ -n "$dark_raw" ] || die "no $want-byte RAW10 file in $dark (saw: $(ls "$dark"/*.bin 2>/dev/null | xargs -r -n1 basename | tr '\n' ' '))"
	[ -n "$neutral_raw" ] || die "no $want-byte RAW10 file in $neutral"

	echo "== $sensor: applying measured black and gains"
	"$TOOL" --sensor "$sensor" --neutral "$neutral_raw" --dark "$dark_raw" \
		--width "$width" --height "$height" --stride "$stride" --cfa "$cfa" --install ||
		die "calibration failed for $sensor"
}

case $WHICH in
	front) run_sensor front ;;
	rear)  run_sensor rear ;;
	both)  run_sensor front; run_sensor rear ;;
esac

echo
echo "Calibration installed. Close and reopen every camera client, then compare"
echo "the same scene. calibrate.py --restore puts the original tuning back."
