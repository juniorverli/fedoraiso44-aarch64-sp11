#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Assisted-by: Claude Sonnet 5.5
#
# Validate libcamera simple-IPA tuning files with libcamera 0.7.2's own YAML parser,
# inside the Fedora 44 container (nothing is installed on the host).
#
#   validate-tuning.sh FILE.yaml [FILE.yaml ...]
#
# Needs: out/ref/libcamera (tag v0.7.2) and out/ref/libcamera-build (meson build of it,
# see ../../evidence/2026-10-31-quality-parity.md "Validation"). Prints counts only.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../../.." && pwd)
ref=$(cd "$repo/out/ref" && pwd -P)
img=${SP11_FEDORA_IMAGE:-sp11-fedora-image:44}
files=()
for f in "$@"; do files+=("$(readlink -f "$f")"); done
dirs=()
for f in "${files[@]}"; do dirs+=(-v "$f:$f:ro"); done
exec docker run --rm --entrypoint bash -v "$ref:/ref" -v "$here/validate-tuning.cpp:/v.cpp:ro" "${dirs[@]}" "$img" -c '
set -e
dnf -y -q install gcc-c++ libyaml-devel >/dev/null 2>&1 || true
B=/ref/libcamera-build; S=/ref/libcamera
g++ -std=c++17 -O1 -DLIBCAMERA_BASE_PRIVATE -o /tmp/validate /v.cpp $S/src/ipa/libipa/interpolator.cpp \
  -I$S/include -I$S/src -I$S/src/ipa -I$B/include -I$B -I$B/include/libcamera \
  -L$B/src/libcamera -L$B/src/libcamera/base -lcamera -lcamera-base \
  -Wl,-rpath,$B/src/libcamera:$B/src/libcamera/base 2>&1 | head -30
/tmp/validate "$@"
' bash "${files[@]}"
