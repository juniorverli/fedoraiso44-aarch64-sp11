#!/usr/bin/env bash
# Offline check: do Qualcomm's downstream hamoa camera DT files (qualcomm-linux/kernel qcom-next,
# stored at out/ref/qcl-hamoa-camx-dts) compile on top of our SP11 DT (v7.3 + kernel/series)?
# The test DTS includes the Denali board DTS, then the downstream .dtsi files, and disables upstream CAMSS.
# dtc reports every label the downstream DT needs that our tree does not define.
#   check-downstream-dt.sh [sensor]     "sensor" also includes hamoa-camera-sensor.dtsi (IMX577 EVK sensors)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
M="$(dirname "$(readlink -f "$REPO/out")")"
SRC=$M/out/linux/spectra; O=$M/out/build/dev-spectra; REF=$M/out/ref/qcl-hamoa-camx-dts
D=$SRC/arch/arm64/boot/dts/qcom
if [[ ${SP11_IN_CONTAINER:-} != 1 ]]; then
  exec 9>"$M/out/.kernel-build.lock"; flock -w 14400 9
  exec "$REPO/scripts/kernel-container.sh" run "$HERE/check-downstream-dt.sh" "$@"
fi
CAM=$M/out/build/spectra-camera-driver
trap 'rm -f "$D"/spectra-dt-test.dts "$D"/hamoa-camera*.dtsi "$SRC"/include/dt-bindings/camera/msm-camera.h; rmdir "$SRC"/include/dt-bindings/camera 2>/dev/null || true' EXIT
mkdir -p "$SRC"/include/dt-bindings/camera; cp "$CAM"/camera/dt-bindings/msm-camera.h "$SRC"/include/dt-bindings/camera/
cp "$REF"/hamoa-camera-regulators.dtsi "$REF"/hamoa-camera.dtsi "$D"/
{ echo '#include "x1p64100-microsoft-denali.dts"'
  echo '#include "hamoa-camera-regulators.dtsi"'
  echo '#include "hamoa-camera.dtsi"'
  if [[ ${1:-} == sensor ]]; then cp "$REF"/hamoa-camera-sensor.dtsi "$D"/; echo '#include "hamoa-camera-sensor.dtsi"'; fi
  echo '&camss { status = "disabled"; };'; } > "$D"/spectra-dt-test.dts
make -C "$SRC" O="$O" ARCH=arm64 DTC_FLAGS_spectra-dt-test="-@ -W no-unit_address_vs_reg" qcom/spectra-dt-test.dtb 2>&1 | grep -vE '^make|^  (HOSTCC|HOSTLD|SYNC|UPD|CC|LD)' | cut -c1-240
