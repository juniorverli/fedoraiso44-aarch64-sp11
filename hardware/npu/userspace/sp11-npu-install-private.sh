#!/bin/bash
# Install the operator's own Qualcomm NPU runtime pieces on a PRIVATE SP11 image.
# Nothing is downloaded. Run it on the installed device only; never inside an image build, never commit its output (S5, QAIRT licence).
# Usage: sudo sp11-npu-install-private.sh --accept-qairt-licence --qairt DIR_OR_ZIP [--ggml-htp FILE] [--shells DIR]
set -euo pipefail

ACCEPT=0; QAIRT=""; GGML_HTP=""; SHELLS=""; DEST=/opt/sp11-npu
FW=/lib/firmware/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn

usage() { sed -n '2,5p' "$0" >&2; exit 2; }
while [ $# -gt 0 ]; do
	case "$1" in
	--accept-qairt-licence) ACCEPT=1 ;;
	--qairt) QAIRT=${2:?}; shift ;;
	--ggml-htp) GGML_HTP=${2:?}; shift ;;
	--shells) SHELLS=${2:?}; shift ;;
	--dest) DEST=${2:?}; shift ;;
	*) usage ;;
	esac
	shift
done
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }
[ "$ACCEPT" -eq 1 ] || { echo "Read the Qualcomm AI Runtime licence you accepted at download, then pass --accept-qairt-licence." >&2; exit 1; }
[ -n "$QAIRT" ] || usage
[ -c /dev/fastrpc-cdsp ] || echo "warning: /dev/fastrpc-cdsp missing (CDSP FastRPC channel not bound); files are installed anyway" >&2

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
if [ -f "$QAIRT" ]; then
	command -v unzip >/dev/null || { echo "install unzip" >&2; exit 1; }
	unzip -q "$QAIRT" -d "$work"; src=$(find "$work" -maxdepth 2 -type d -name 'qairt*' | head -n1); src=${src:-$work}
else
	src=$QAIRT
fi
skel=$(find "$src" -path '*hexagon-v73/unsigned/libQnnHtpV73Skel.so' | head -n1)
host=$(find "$src" -path '*aarch64*' -name libQnnHtp.so | head -n1)
[ -n "$skel" ] && [ -n "$host" ] || { echo "QAIRT tree lacks hexagon-v73/unsigned/libQnnHtpV73Skel.so or an aarch64 libQnnHtp.so" >&2; exit 1; }
echo "QAIRT skel: $skel"; echo "QAIRT host: $host"

install -d -m 0755 "$DEST/lib/host" "$DEST/lib/dsp"
hostdir=$(dirname "$host")
for f in libQnnHtp.so libQnnCpu.so libQnnSystem.so libQnnHtpPrepare.so libQnnHtpV73Stub.so; do
	[ -f "$hostdir/$f" ] && install -m 0644 "$hostdir/$f" "$DEST/lib/host/"
done
install -m 0644 "$skel" "$DEST/lib/dsp/"
[ -f "$(dirname "$skel")/libQnnHtpV73SkelDrv.so" ] && install -m 0644 "$(dirname "$skel")/libQnnHtpV73SkelDrv.so" "$DEST/lib/dsp/"
[ -n "$GGML_HTP" ] && install -m 0644 "$GGML_HTP" "$DEST/lib/dsp/libggml-htp-v73.so"

# Shell and firmware must be the same build (reference NPU.md: mismatch corrupts GLINK framing on session open).
fwid=$(strings -n 8 "$FW" 2>/dev/null | grep -m1 -o '^QC_IMAGE_VERSION_STRING=.*' | cut -d= -f2 || true)
echo "CDSP firmware build: ${fwid:-unknown}"
if [ -n "$SHELLS" ]; then
	for f in fastrpc_shell_3 fastrpc_shell_unsigned_3; do
		[ -f "$SHELLS/$f" ] || continue
		sid=$(strings -n 8 "$SHELLS/$f" | grep -m1 -o 'CDSP\.HT[0-9.a-z]*-[0-9.]*-HAMOA-1' || true)
		fid=$(printf %s "$fwid" | grep -o 'CDSP\.HT[0-9.a-z]*-[0-9.]*-HAMOA-1' || true)
		if [ -n "$fid" ] && [ "$sid" != "$fid" ]; then echo "refusing $f: build '$sid' differs from firmware '$fid'" >&2; exit 1; fi
		install -D -m 0644 "$SHELLS/$f" "$DEST/lib/dsp/$f"
	done
fi
cat >/etc/profile.d/sp11-npu.sh <<P
export QNN_SDK_ROOT=$DEST
export LD_LIBRARY_PATH=$DEST/lib/host\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}
export ADSP_LIBRARY_PATH=$DEST/lib/dsp:/usr/lib/dsp/cdsp\${ADSP_LIBRARY_PATH:+:\$ADSP_LIBRARY_PATH}
P
echo "installed under $DEST. Join group fastrpc to use /dev/fastrpc-cdsp. This script never writes remoteproc state."
