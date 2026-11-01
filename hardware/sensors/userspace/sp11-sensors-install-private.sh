#!/bin/bash
# Install the staged private sensor tree (output of sp11-sensors-stage.sh) into a rootfs or the running system.
# PRIVATE only (S5). The RPMs (hexagonrpcd, libssc, libssc-tools, iio-sensor-proxy, sp11-sensors) are installed
# separately; this step only adds the Windows-derived data they serve.
# Usage: sp11-sensors-install-private.sh --stage DIR [--root ROOT] [--registry empty|seed|keep]
#   --root      target root (default /)
#   --registry  seed (default): copy registry-seed/ into /var/lib/hexagonrpcd/registry when that directory is empty;
#               empty: leave it empty so the ADSP generates the registry (needs the write-capable hexagonrpcd);
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
rm -rf "$dest/sensors/config" "$dest/socinfo"
install -d -m 0755 "$dest/sensors/config" "$dest/socinfo"
cp -a "$STAGE/sensors/config/." "$dest/sensors/config/"
install -m 0644 "$STAGE/sensors/sns_reg.conf" "$dest/sensors/sns_reg.conf"
cp -a "$STAGE/socinfo/." "$dest/socinfo/"
# hexagonrpcd serves <root>/sensors/registry as /persist/sensors/registry/registry: a symlink to the state
# directory keeps /usr read-only and the registry writable (StateDirectory= of the unit creates the target).
rm -rf "$dest/sensors/registry"
ln -s /var/lib/hexagonrpcd/registry "$dest/sensors/registry"
find "$dest" -type d -exec chmod 0755 {} +
find "$dest" -type f -exec chmod 0644 {} +

install -d -m 0750 "$state"
if [ "$MODE" = seed ] && [ -d "$STAGE/registry-seed" ] && [ -z "$(ls -A "$state")" ]; then
	cp -a "$STAGE/registry-seed/." "$state/"
	find "$state" -type f -exec chmod 0640 {} +
fi
echo "installed: $(find "$dest/sensors/config" -type f | wc -l) config files, $(ls "$dest/socinfo" | wc -l) identity files, registry state files: $(ls "$state" | wc -l) (mode $MODE)"
echo "ownership of $ROOT/var/lib/hexagonrpcd: the unit's StateDirectory= sets it to hexagonrpcd:fastrpc at the first start"
