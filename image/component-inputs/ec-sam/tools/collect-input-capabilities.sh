#!/usr/bin/env bash
# Run as root on the live image. Output contains capabilities, never input events.
# Fedora packages: libinput-utils, evtest, coreutils, gawk.
set -u

for tool in libinput evtest timeout stdbuf awk; do
    command -v "$tool" >/dev/null || exit 1
done

libinput list-devices
capture_rc=$?
for event in /sys/class/input/event*; do
    path=$(readlink -f "$event/device")
    case "$path" in
        *surface_aggregator_platform_hub*|*gpio-keys*|*pmic_pwrkey*) ;;
        *) continue ;;
    esac
    node="/dev/input/${event##*/}"
    printf '\n== %s capabilities ==\n' "$node"
    # evtest has no capabilities-only option. Stop output at its header boundary,
    # before the event loop; timeout also ends a producer waiting for an event.
    # Never use --grab, --query EV_KEY, or libinput debug-events here.
    timeout 2s stdbuf -oL evtest "$node" 2>&1 |
        awk '/^Testing / { exit } /^Event:/ { next } { print }'
    result=("${PIPESTATUS[@]}")
    case "${result[0]}" in
        0|124|141) ;; # Normal exit, timeout, or pipe closed at header boundary.
        *) capture_rc=1 ;;
    esac
    [[ ${result[1]} == 0 ]] || capture_rc=1
done
exit "$capture_rc"
