#!/usr/bin/env bash
# Generator hook for the closed-loop speaker protection data (private, S5/D25).
#
#   build-closedloop.sh [--with-cps] [--nominal-cal | --measured RL RR TL TR]
#
# Writes into out/firmware-private/audio/qcom/x1e80100/ (git-ignored, mode 0600):
#   X1E80100-Microsoft-Surface-Pro-11-sp11cl.bin    control links + calibration records
#   X1E80100-Microsoft-Surface-Pro-11-sp11cal.bin   unit R0/T0, only with --nominal-cal or --measured
# These are Windows-derived. They are installed only by the private image mode
# (image-build.sh --private), never by the public ISO, never committed. Without a
# sp11cal file the kernel keeps the speakers muted (safe default).
#
# The topology .bin (SP/VI/CPS chains) is NOT produced here: its host tap is an open
# design question, see evidence/2026-10-30-closed-loop.md section 6.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
main=${SP11_MAIN:-$(git -C "$here" rev-parse --git-common-dir | xargs dirname)}
acdb="$main/sources/windows/DriverStore/surface_acsp8380.inf_arm64_f6524e4db745e12a/REV_0D/acdb_cal_0D.acdb"
out="${SP11_PRIVATE_AUDIO:-$main/out/firmware-private/audio}"
[[ -f $acdb ]] || { echo "missing $acdb" >&2; exit 1; }
exec python3 -I "$here/sp11_closedloop.py" --acdb "$acdb" --out-dir "$out" --self-test "$@"
