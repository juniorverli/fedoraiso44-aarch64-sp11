#!/usr/bin/env bash
# Generator hook for the closed-loop speaker protection data (private, S5/D25).
#
#   build-closedloop.sh [--with-cps] [--nominal-cal | --measured RL RR TL TR]
#   SP11_TOPOLOGY=1 build-closedloop.sh ...     also build the closed-loop topology (container, network)
#
# Writes into out/firmware-private/audio/qcom/x1e80100/ (git-ignored, mode 0600):
#   X1E80100-Microsoft-Surface-Pro-11-sp11cl.bin    control links + calibration records
#   X1E80100-Microsoft-Surface-Pro-11-sp11cal.bin   unit R0/T0, only with --nominal-cal or --measured
#   X1E80100-Microsoft-Surface-Pro-11-tplg.bin      (SP11_TOPOLOGY=1) public topology + SP/VI chains: it REPLACES
#                                                   the public file of the same name in the private image only
#   sp11-ids.m4, X1E80100-Microsoft-Surface-Pro-11-closedloop.conf   inputs/audit of the topology build
# These are Windows-derived. They are installed only by the private image mode
# (image-build.sh --private), never by the public ISO, never committed. Without a
# sp11cal file the kernel keeps the speakers muted (safe default).
#
# The topology needs no host tap: the sense chain ends in SP_VI inside the DSP, and a trigger front
# end only makes DPCM open it (evidence/2026-10-31-topology-rfc.md). CPS is not in the topology.
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
