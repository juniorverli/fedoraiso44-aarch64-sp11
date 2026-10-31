#!/usr/bin/env bash
# Build the Surface Pro 11 topology WITH the closed-loop speaker protection chains (private, S5/D25).
#
#   build-closedloop-topology.sh IDS_M4 OUT_DIR
#
# IDS_M4  the private sp11-ids.m4 written by `sp11_closedloop.py --emit-ids` (Windows ACDB derived)
# OUT_DIR where qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin and the .conf are written
#         (normally out/firmware-private/audio; the file replaces the public topology of the same
#         name in the private image only)
#
# Source: linux-msm/audioreach-topology at the commit pinned in ../build-topology.sh, plus the m4
# overlay in ./m4 (module widgets, WSA playback with SP, sense back end, trigger front end).
# Runs in a Fedora 44 container; nothing is installed on the host.
set -euo pipefail
ids=${1:?usage: build-closedloop-topology.sh IDS_M4 OUT_DIR}
out=${2:?usage: build-closedloop-topology.sh IDS_M4 OUT_DIR}
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
commit=aab5c37c4fb9d9daed2dc789b8b7ca91c4133899
mkdir -p "$out"
docker run --rm -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
  -v "$here/m4":/overlay:ro -v "$(cd "$(dirname "$ids")" && pwd)/$(basename "$ids")":/ids/sp11-ids.m4:ro \
  -v "$(cd "$out" && pwd)":/out registry.fedoraproject.org/fedora:44 bash -ec '
dnf -q -y install git m4 alsa-topology-utils >/dev/null
git clone -q https://github.com/linux-msm/audioreach-topology.git /tmp/art
cd /tmp/art && git checkout -q '"$commit"'
cp /overlay/module_sp11.m4 /overlay/subgraph-sp11-*.m4 audioreach/
cp /overlay/X1E80100-Microsoft-Surface-Pro-11-closedloop.m4 /ids/sp11-ids.m4 .
d=qcom/x1e80100; n=X1E80100-Microsoft-Surface-Pro-11
mkdir -p b/$d
m4 -I b -I . X1E80100-Microsoft-Surface-Pro-11-closedloop.m4 > b/$d/$n.conf
alsatplg -c b/$d/$n.conf -o b/$d/$n-tplg.bin
install -D -m 0600 b/$d/$n-tplg.bin /out/$d/$n-tplg.bin
install -D -m 0600 b/$d/$n.conf /out/$d/$n-closedloop.conf
chown -R $HOST_UID:$HOST_GID /out/$d
sha256sum /out/$d/$n-tplg.bin'
