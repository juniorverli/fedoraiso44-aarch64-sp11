#!/usr/bin/env bash
# Build the Surface Pro 11 AudioReach topology from the upstream source in a Fedora 44 container.
# Source: linux-msm/audioreach-topology, commit aab5c37c4fb9d9daed2dc789b8b7ca91c4133899
#         (merge of PR 76, 2026-09-14). Output name is what sound/soc/qcom/qdsp6/topology.c:1422 requests:
#         qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin
# Expected SHA-256 (built 2026-10-30 with alsa-topology-utils 1.2.16):
#         b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03
# The topology has NO speaker protection (SP/VI) modules. Owner of the install path: image/firmware worker.
set -euo pipefail
out=${1:?usage: build-topology.sh OUT_DIR}
mkdir -p "$out"
docker run --rm -v "$(cd "$out" && pwd)":/out registry.fedoraproject.org/fedora:44 bash -ec '
dnf -q -y install git cmake m4 make gcc gcc-c++ alsa-topology-utils >/dev/null
git clone -q https://github.com/linux-msm/audioreach-topology.git /tmp/art
cd /tmp/art && git checkout -q aab5c37c4fb9d9daed2dc789b8b7ca91c4133899
mkdir b && cd b && cmake .. >/dev/null && make -j4 >/dev/null 2>&1 || true
f=qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin
test -f $f
install -D -m 0644 $f /out/$f
sha256sum /out/$f'
