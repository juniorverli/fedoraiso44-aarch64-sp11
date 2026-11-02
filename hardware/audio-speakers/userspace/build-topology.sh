#!/usr/bin/env bash
# Build the Surface Pro 11 AudioReach topology from the upstream source in a Fedora 44 container.
# Source: linux-msm/audioreach-topology, commit 993a17dcb672357998a463a73f120064d6c74f4f
#         (D28 reference pin). Output name is what sound/soc/qcom/qdsp6/topology.c requests:
#         qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin
# The binary hash for this pin/toolchain must be recorded after the image owner builds it;
# the older aab5c37 build hash does not establish identity at this pin.
# The topology has NO speaker protection (SP/VI) modules. Owner of the install path: image/firmware worker.
# Closed-loop data (private, Windows-derived): build-topology/build-closedloop.sh, see evidence/2026-10-30-closed-loop.md.
set -euo pipefail
out=${1:?usage: build-topology.sh OUT_DIR}
mkdir -p "$out"
docker run --rm -v "$(cd "$out" && pwd)":/out registry.fedoraproject.org/fedora:44 bash -ec '
dnf -q -y install git cmake m4 make gcc gcc-c++ alsa-topology-utils >/dev/null
git clone -q https://github.com/linux-msm/audioreach-topology.git /tmp/art
cd /tmp/art && git checkout -q 993a17dcb672357998a463a73f120064d6c74f4f
mkdir b && cd b && cmake .. >/dev/null && make -j4 >/dev/null 2>&1 || true
f=qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin
test -f $f
install -D -m 0644 $f /out/$f
sha256sum /out/$f'
