#!/usr/bin/env bash
# Generator hook for the closed-loop speaker protection data (private, S5/D25).
#
#   build-closedloop.sh --vi-only-diagnostic [--nominal-cal]
#   SP11_TOPOLOGY=1 build-closedloop.sh ...     also build the closed-loop topology (container, network)
#
# Writes into out/firmware-private/audio/qcom/x1e80100/ (git-ignored, mode 0600):
#   X1E80100-Microsoft-Surface-Pro-11-sp11cl.bin    control links + calibration records
#   X1E80100-Microsoft-Surface-Pro-11-sp11cal.bin   test-only nominal R0/T0 if requested
#   X1E80100-Microsoft-Surface-Pro-11-tplg.bin      (SP11_TOPOLOGY=1) public topology plus SP/VI chains;
#                                                   image staging must rename it to the CL model name
#   sp11-ids.m4, X1E80100-Microsoft-Surface-Pro-11-closedloop.conf   inputs/audit of the topology build
# These are Windows-derived. They are installed only by the private image mode
# (image-build.sh --private), never by the public ISO, never committed. Without a
# sp11cal file the kernel keeps the speakers muted (safe default).
#
# The proposed DSP sense chain ends in SP_VI; the DAPM-only trigger does not provide host VI data.
# This has not been validated on the device. CPS is absent and its guard bit is required.
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
main=${SP11_MAIN:-$(git -C "$here" rev-parse --git-common-dir | xargs dirname)}
acdb="$main/sources/windows/DriverStore/surface_acsp8380.inf_arm64_f6524e4db745e12a/REV_0D/acdb_cal_0D.acdb"
out="${SP11_PRIVATE_AUDIO:-$main/out/firmware-private/audio}"
[[ -f $acdb ]] || { echo "missing $acdb" >&2; exit 1; }
python3 -I "$here/sp11_closedloop.py" --acdb "$acdb" --out-dir "$out" --self-test "$@"
if [[ ${SP11_TOPOLOGY:-0} == 1 ]]; then
  python3 -I "$here/sp11_closedloop.py" --acdb "$acdb" --out-dir "$out" --emit-ids "$out/sp11-ids.m4"
  bash "$here/build-closedloop-topology.sh" "$out/sp11-ids.m4" "$out"
fi
