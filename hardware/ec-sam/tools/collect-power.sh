#!/usr/bin/env bash
# Run on the live image, once per named charger state. No identity or limits read.
set -uo pipefail

command -v upower >/dev/null || exit 1

date -u +%FT%TZ
for supply in /sys/class/power_supply/*; do
    [[ -d "$supply" ]] || continue
    printf '\n== %s ==\n' "${supply##*/}"
    for attr in type present status capacity capacity_level online energy_now \
                energy_full energy_full_design power_now voltage_now cycle_count; do
        if [[ -r "$supply/$attr" ]]; then
            printf '%s=' "$attr"
            cat "$supply/$attr"
        fi
    done
done
printf '\n== UPower ==\n'
LC_ALL=C upower -d | awk '
    /^Device:/ || /^[[:space:]]*(native-path|power supply|updated|has history|has statistics|present|rechargeable|state|warning-level|energy|energy-empty|energy-full|energy-full-design|energy-rate|voltage|charge-cycles|time to empty|time to full|percentage|capacity|technology|online|on-battery|lid-is-closed|lid-is-present):/ { print }
'
