#!/bin/bash
# Install the staged private sensor tree (output of sp11-sensors-stage.sh) into a rootfs or the running system.
# PRIVATE only (S5). The RPMs (hexagonrpcd, libssc, libssc-tools, iio-sensor-proxy, sp11-sensors) are installed
# separately; this step only adds the Windows-derived data they serve.
# Usage: sp11-sensors-install-private.sh --stage DIR [--root ROOT] [--registry empty|seed|keep]
#   --root      target root (default /)
#   --registry  seed (default): copy registry-seed/ into the registry child only if it does not already exist;
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
child="$state/registry"
if [ "$MODE" = seed ] && [ -d "$STAGE/registry-seed" ] && [ ! -e "$child" ] && [ ! -L "$child" ]; then
	# Resolve IDs in the target root, never the build host. Refuse to guess.
	uid=$(awk -F: '$1 == "hexagonrpcd" {print $3; exit}' "$ROOT/etc/passwd")
	gid=$(awk -F: '$1 == "fastrpc" {print $3; exit}' "$ROOT/etc/group")
	[[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || { echo "target hexagonrpcd:fastrpc account missing" >&2; exit 1; }
	tmp=$(mktemp -d "$state/.sp11-seed.XXXXXX")
	trap 'rm -rf "$tmp"' EXIT
	cp -a "$STAGE/registry-seed/." "$tmp/"
	find "$tmp" -type d -exec chmod 0750 {} +
	find "$tmp" -type f -exec chmod 0640 {} +
	chown -R "$uid:$gid" "$tmp"
	# No replacement of existing state, including a concurrent creator.
	mv -T -n "$tmp" "$child"
	[ ! -e "$tmp" ] || { echo "registry child appeared during seeding; left untouched" >&2; exit 1; }
	trap - EXIT
fi
echo "installed: $(find "$dest/sensors/config" -type f | wc -l) config files, $(ls "$dest/socinfo" | wc -l) identity files, registry child files: $(find "$child" -maxdepth 1 -type f 2>/dev/null | wc -l) (mode $MODE)"
