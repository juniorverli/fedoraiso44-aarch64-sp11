#!/bin/bash
# Install the staged private sensor tree (output of sp11-sensors-stage.sh) into a rootfs or the running system.
# PRIVATE only (S5). The RPMs (hexagonrpcd, libssc, libssc-tools, iio-sensor-proxy, sp11-sensors) are installed
# separately; this step only adds the Windows-derived data they serve.
# Usage: sp11-sensors-install-private.sh --stage DIR [--root ROOT] [--registry empty|seed|keep]
#   --root      target root (default /)
#   --registry  seed (default): copy registry-seed/ into the configured registry/ child when it is empty;
#               empty: leave the configured registry/ child empty so the ADSP generates it;
#               keep: touch nothing there.
set -euo pipefail
STAGE=""; ROOT=/; MODE=seed
while [ $# -gt 0 ]; do
	case "$1" in
	--stage) STAGE=${2:?}; shift ;;
	--root) ROOT=${2:?}; shift ;;
	--registry) MODE=${2:?}; shift ;;
	*) sed -n '2,10p' "$0" >&2; exit 2 ;;
	esac
	shift
done
[ -d "$STAGE/sensors/config" ] && [ -d "$STAGE/socinfo" ] || { echo "$STAGE is not a staged sensor tree" >&2; exit 1; }
( cd "$STAGE" && sha256sum -c --quiet SHA256SUMS ) || { echo "staged tree fails its SHA256SUMS" >&2; exit 1; }
case "$MODE" in empty|seed|keep) ;; *) echo "bad --registry" >&2; exit 2 ;; esac

dest="$ROOT/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11"
state="$ROOT/var/lib/hexagonrpcd/registry"
registry="$state/registry"
rm -rf "$dest/sensors/config" "$dest/socinfo"
install -d -m 0755 "$dest/sensors/config" "$dest/socinfo"
cp -a "$STAGE/sensors/config/." "$dest/sensors/config/"
install -m 0644 "$STAGE/sensors/sns_reg.conf" "$dest/sensors/sns_reg.conf"
cp -a "$STAGE/socinfo/." "$dest/socinfo/"
# sns_reg.conf sets output=/persist/sensors/registry/registry. hexagonrpcd maps
# /persist/sensors/registry to <root>/sensors/registry, so the JSON registry
# belongs in the nested registry/ directory. Keep ADSP state files that use
# the parent path in $state; both remain writable through the same symlink.
rm -rf "$dest/sensors/registry"
ln -s /var/lib/hexagonrpcd/registry "$dest/sensors/registry"
find "$dest" -type d -exec chmod 0755 {} +
find "$dest" -type f -exec chmod 0644 {} +

install -d -m 0750 "$state" "$registry"
if [ "$MODE" = seed ] && [ -d "$STAGE/registry-seed" ] && [ -z "$(ls -A "$registry")" ]; then
	cp -a "$STAGE/registry-seed/." "$registry/"
	# These generated seed entries are read-only inputs (matching sscregistrygen's
	# 0644 output); ADSP-created state files are written separately by the daemon.
	find "$registry" -type f -exec chmod 0644 {} +
fi
echo "installed: $(find "$dest/sensors/config" -type f | wc -l) config files, $(ls "$dest/socinfo" | wc -l) identity files, registry files: $(find "$registry" -type f | wc -l), parent state files: $(find "$state" -maxdepth 1 -type f | wc -l) (mode $MODE)"
echo "ownership of $ROOT/var/lib/hexagonrpcd: the unit's StateDirectory= sets it to hexagonrpcd:fastrpc at the first start"
