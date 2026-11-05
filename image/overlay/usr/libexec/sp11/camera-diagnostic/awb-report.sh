#!/bin/bash
# Report the white-balance gains the Software ISP actually applies, per camera.
#
# Run on the `safe` entry with every camera client closed. It turns on the
# normally-Debug `IPASoftAwb` log for one short capture per camera, parses the
# last `gain R/B` line and classifies it:
#
#   AWB_STUCK    gains are 1.0/1.0: the estimator is not updating, so the raw
#                sensor response stays green whatever the tuning says.
#   AWB_CEILING  a gain sits at the tuning's ceiling (4.0 stock, or maxGains):
#                the estimator saturated.
#   AWB_OK       plausible gains: white balance runs; a remaining cast is the
#                scene, the black pedestal or the calibration.
#   AWB_NO_LINE  no gain line at all: the capture or the IPA did not run.
#
# It does not save frames, read samples, change controls or touch the LED. A
# person must watch the privacy indicator; press Ctrl-C on any doubt.
#
# Exit status 0 only when both cameras produced a gain line.

set -uo pipefail

YAML_DIR=${SP11_AWB_REPORT_YAML_DIR:-/usr/share/libcamera/ipa/simple}
OUT=${SP11_AWB_REPORT_OUT:-/var/tmp/sp11-awb-report.txt}
SAFE_ENV=(LIBCAMERA_SOFTISP_MODE=cpu GALLIUM_DRIVER=softpipe LIBGL_ALWAYS_SOFTWARE=1)

die() { echo "awb-report: $*" >&2; exit 1; }

parse_gain() { # file -> "r g b cct" (last line) or empty
	local line
	line=$(grep -o 'gain R/B: Vector { [0-9.]*, [0-9.]*, [0-9.]*  }; temperature: [0-9]*' "$1" 2>/dev/null | tail -n1)
	[ -n "$line" ] || return 0
	printf '%s\n' "$line" |
		sed -E 's/.*Vector \{ ([0-9.]+), ([0-9.]+), ([0-9.]+)  \}; temperature: ([0-9]+).*/\1 \2 \3 \4/'
}

ceiling() { # yaml -> "r b" from maxGains, else stock 4.0 4.0
	local line
	line=$(grep -E '^[[:space:]]+maxGains:[[:space:]]*\[' "$1" 2>/dev/null | tail -n1)
	if [ -n "$line" ]; then
		printf '%s\n' "$line" | sed -E 's/.*\[ ([0-9.]+), [0-9.]+, ([0-9.]+) \].*/\1 \2/'
	else
		echo "4.0 4.0"
	fi
}

verdict() { # r g b ceil_r ceil_b
	awk -v r="$1" -v g="$2" -v b="$3" -v cr="$4" -v cb="$5" 'BEGIN {
		if (r <= 0 || g <= 0 || b <= 0) { print "AWB_NO_LINE"; exit }
		if (r > 0.98 && r < 1.02 && b > 0.98 && b < 1.02) { print "AWB_STUCK"; exit }
		if (r >= cr - 0.01 || b >= cb - 0.01) { print "AWB_CEILING"; exit }
		print "AWB_OK"
	}'
}

id_for() { # listing, cci address -> camera index
	printf '%s\n' "$1" |
		sed -nE "s/^([0-9]+):.*\\(\\/base\\/soc@0\\/cci@$2\\/i2c-bus@1\\/camera@10\\).*/\\1/p" |
		head -n1
}

self_test() {
	local failures=0 got
	check() { # label, expected, actual
		if [ "$2" = "$3" ]; then echo "PASS $1"; else echo "FAIL $1: expected $2 got $3"; failures=$((failures + 1)); fi
	}
	local sample='[0:00:01.000] INFO IPASoftAwb awb.cpp:93 gain R/B: Vector { 4, 1, 4  }; temperature: 5000'
	check parse "1.5 1 2.25 4200" "$(printf '%s\n' '[x] gain R/B: Vector { 1.5, 1, 2.25  }; temperature: 4200' >/tmp/awb-st.$$; parse_gain /tmp/awb-st.$$; rm -f /tmp/awb-st.$$)"
	check stuck "AWB_STUCK" "$(verdict 1.0 1.0 1.0 9.83 4.71)"
	check ceiling_r "AWB_CEILING" "$(verdict 9.83 1 1.2 9.83 4.71)"
	check ceiling_b "AWB_CEILING" "$(verdict 1.4 1 4.71 9.83 4.71)"
	check ok "AWB_OK" "$(verdict 2.2 1 1.6 9.83 4.71)"
	check stock_ceiling "AWB_CEILING" "$(verdict 4.0 1 1.5 4.0 4.0)"
	local y=/tmp/awb-st-yaml.$$
	printf '  - Awb:\n      maxGains: [ 9.83, 1.0, 4.71 ]\n' >"$y"
	check yaml "9.83 4.71" "$(ceiling "$y")"
	rm -f "$y"
	local l='0: Internal back camera (/base/soc@0/cci@ac15000/i2c-bus@1/camera@10)
1: Internal front camera (/base/soc@0/cci@ac16000/i2c-bus@1/camera@10)'
	check id_rear "0" "$(id_for "$l" ac15000)"
	check id_front "1" "$(id_for "$l" ac16000)"
	[ -z "$sample" ] || true
	return "$failures"
}

if [ "${1:-}" = "--self-test" ]; then
	self_test
	exit $?
fi

# Host tests set SP11_AWB_REPORT_TEST=1 to skip the entry and terminal gates;
# on the image the safe entry and an observing person are mandatory.
if [ "${SP11_AWB_REPORT_TEST:-0}" != 1 ]; then
	case " $(cat /proc/cmdline) " in
		*' sp11.entry=safe '*) ;;
		*) die "not the safe entry (sp11.entry=safe required)" ;;
	esac
	[ -t 0 ] || die "an interactive terminal and an observer are required"
	cat <<'EOF'
Close Snapshot and every other camera client. The privacy indicator will turn
on while each capture runs: a person must watch it and press Ctrl-C at once if
it stays dark, on a fault or on a reset. No LED, flash or control override is
used. Nothing is saved.
EOF
	read -r answer || die "no answer"
	[ "$answer" = OBSERVING ] || die "cancelled before streaming"
fi

listing=""
for try in 1 2 3; do
	listing=$(timeout -k 1 8 env "${SAFE_ENV[@]}" cam -l 2>&1) && \
		[ -n "$(id_for "$listing" ac15000)" ] && [ -n "$(id_for "$listing" ac16000)" ] && break
	sleep 2
done
front_id=$(id_for "$listing" ac16000)
rear_id=$(id_for "$listing" ac15000)
[ -n "$front_id" ] || die "front camera (ac16000) not enumerated"
[ -n "$rear_id" ] || die "rear camera (ac15000) not enumerated"

: >"$OUT"
chmod 0600 "$OUT" 2>/dev/null || true
status=0
for pair in "front:$front_id:imx681" "rear:$rear_id:ov13858"; do
	name=${pair%%:*}
	rest=${pair#*:}
	id=${rest%%:*}
	sensor=${rest##*:}
	log=$(mktemp /tmp/awb-report.XXXXXX)
	timeout -k 1 30 env "${SAFE_ENV[@]}" LIBCAMERA_LOG_LEVELS='IPASoftAwb:DEBUG' \
		cam -c "$id" --capture=10 >"$log" 2>&1
	read -r ceil_r ceil_b < <(ceiling "$YAML_DIR/$sensor.yaml")
	gains=$(parse_gain "$log")
	if [ -z "$gains" ]; then
		result=AWB_NO_LINE
		echo "$name ($sensor, camera $id): no gain line; capture exit $?" | tee -a "$OUT"
		status=1
	else
		# shellcheck disable=SC2086
		set -- $gains
		result=$(verdict "$1" "$2" "$3" "$ceil_r" "$ceil_b")
		printf '%s (%s, camera %s): gains %s %s %s, CCT %s K, ceiling %s/%s -> %s\n' \
			"$name" "$sensor" "$id" "$1" "$2" "$3" "$4" "$ceil_r" "$ceil_b" "$result" | tee -a "$OUT"
	fi
	rm -f "$log"
	case $result in AWB_OK) ;; *) status=1 ;; esac
done
echo "saved $OUT (mode 0600); send only the lines above" >&2
exit "$status"
