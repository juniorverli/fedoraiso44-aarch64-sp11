#!/usr/bin/env bash
# Fetch qcom/x1e80100/CAMERA_ICP.mbn from Qualcomm's own Linux package (private image build step).
#
#   hardware/cameras/spectra/rpm/fetch-camera-icp.sh [DEST]
#
# DEST defaults to out/firmware-private/cameras/spectra. Writes
#   DEST/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn
#   DEST/lib/firmware/LICENSE.qcom-2      (Qualcomm-Nologin-Binaries, ships with the binary)
#   DEST/SHA256SUMS
# The blob is Qualcomm's redistributable-in-binary-form firmware for Qualcomm-chipset platforms; it is NEVER put in
# git (the image fetches it at build time, in private mode only). Both pins below are checked before anything is
# installed; a mismatch aborts and writes nothing.
#
# Source (anonymous download, Artifactory): package camxfirmware 1.0.27, Qualcomm CamX release 261026, "resolute"
# (Debian-format) prebuilt, member camxfirmware-hamoa (the purwa x1p42100 package symlinks to the same file).
set -euo pipefail
URL=https://qartifactory-edge.qualcomm.com/artifactory/qsc_releases/software/chip/component/camx.qclinux.0.0/261026/prebuilt_resolute/camxfirmware_1.0.27_arm64.tar.gz
TAR_SHA256=1f054c4700a3d936924f94a1fa3bbd7a51e15df8d86de9ea332c5d2533d04437
MEMBER=camxfirmware-1.0.27/camxfirmware-hamoa/arm64/usr/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn
MBN_SHA256=4a75fd1ae5b47960698e3b5bd614a0484f05c068144f4e603332ab6e746ef4c8
MBN_BYTES=541336
LICENSE_MEMBER=camxfirmware-1.0.27/LICENSE.qcom-2

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
OUT="${SP11_OUT:-$(readlink -f "$REPO/out")}"
dest=${1:-$OUT/firmware-private/cameras/spectra}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cache=$OUT/ref/qcl-camx-prebuilt/camxfirmware_1.0.27_arm64.tar.gz   # reuse the local copy when it matches the pin
if [[ -f $cache ]] && [[ $(sha256sum < "$cache" | cut -d' ' -f1) == "$TAR_SHA256" ]]; then
  cp "$cache" "$tmp/pkg.tar.gz"
else
  curl --fail --location --retry 3 --silent --show-error "$URL" -o "$tmp/pkg.tar.gz"
fi
printf '%s  %s\n' "$TAR_SHA256" "$tmp/pkg.tar.gz" | sha256sum -c - >/dev/null || { echo "fetch-camera-icp: package sha256 mismatch" >&2; exit 1; }
tar -xzOf "$tmp/pkg.tar.gz" "$MEMBER" > "$tmp/CAMERA_ICP.mbn"
tar -xzOf "$tmp/pkg.tar.gz" "$LICENSE_MEMBER" > "$tmp/LICENSE.qcom-2"
printf '%s  %s\n' "$MBN_SHA256" "$tmp/CAMERA_ICP.mbn" | sha256sum -c - >/dev/null || { echo "fetch-camera-icp: CAMERA_ICP.mbn sha256 mismatch" >&2; exit 1; }
[[ $(stat -c %s "$tmp/CAMERA_ICP.mbn") == "$MBN_BYTES" ]] || { echo "fetch-camera-icp: CAMERA_ICP.mbn size mismatch" >&2; exit 1; }
install -Dm0644 "$tmp/CAMERA_ICP.mbn" "$dest/lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn"
install -Dm0644 "$tmp/LICENSE.qcom-2" "$dest/lib/firmware/LICENSE.qcom-2"
( cd "$dest" && sha256sum lib/firmware/qcom/x1e80100/CAMERA_ICP.mbn lib/firmware/LICENSE.qcom-2 > SHA256SUMS && cat SHA256SUMS )
