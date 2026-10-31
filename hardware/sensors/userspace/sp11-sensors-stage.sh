#!/bin/bash
# Stage the SSC sensor tree for hexagonrpcd from the operator's own Windows driver dump.
# PRIVATE only (S5): the output is Windows/Qualcomm material. Write it under out/ (never git, never the public
# ISO); sp11-sensors-install-private.sh copies it into an image or a rootfs.
#
# Usage: sp11-sensors-stage.sh --windows DIR --out DIR [--registry-gen PATH] [--no-seed]
#                              [--registry-from DIR] [--soc-id N] [--revision R]
#   --windows        sources/windows (contains DriverStore/)
#   --out            new output directory, under an out/ directory or /tmp
#   --registry-gen   sscregistrygen from the hexagonrpcd package (default: found in PATH)
#   --no-seed        do not pre-generate the registry; the ADSP must create it (needs the write-capable
#                    hexagonrpcd of this package set)
#   --registry-from  a real pre-parsed registry directory (e.g. a captured Windows DriverData\Qualcomm\fastRPC\
#                    persist\sensors\registry\registry); used instead of generating
#   --soc-id/--revision  override the identity files (default: the Windows package values)
#
# Output layout (the root that hexagonrpcd gets with -R; install it at
# /usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/):
#   sensors/config/        70 files: JSON, .bin, .pb, json.lst (what the ADSP opens under /vendor/etc/sensors/config)
#   sensors/sns_reg.conf   the package's sns_reg_config (served as /vendor/etc/sensors/sns_reg_config), paths unchanged
#   socinfo/               the six identity files hexagonrpcd serves as /sys/devices/soc0/*
#   registry-seed/         pre-generated registry files (optional)
set -euo pipefail
WIN=""; OUT=""; GEN=""; REG=""; SEED=1; SOC=""; REV=""
while [ $# -gt 0 ]; do
	case "$1" in
	--windows) WIN=${2:?}; shift ;;
	--out) OUT=${2:?}; shift ;;
	--registry-gen) GEN=${2:?}; shift ;;
	--registry-from) REG=${2:?}; shift ;;
	--no-seed) SEED=0 ;;
	--soc-id) SOC=${2:?}; shift ;;
	--revision) REV=${2:?}; shift ;;
	*) sed -n '2,19p' "$0" >&2; exit 2 ;;
	esac
	shift
done
[ -n "$WIN" ] && [ -n "$OUT" ] || { sed -n '2,19p' "$0" >&2; exit 2; }
case "$(readlink -f "$OUT")" in */out/*|/tmp/*|/var/tmp/*) ;; *) echo "refusing: --out must be under an out/ directory or /tmp" >&2; exit 1 ;; esac
[ -e "$OUT" ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ] && { echo "refusing: $OUT is not empty" >&2; exit 1; }

pkg=$(ls -d "$WIN"/DriverStore/surfacepro_snscfgcrd8380.inf_arm64_* 2>/dev/null | grep -v '\.ini$' | head -n1)
[ -d "$pkg" ] || { echo "surfacepro_snscfgcrd8380 package not found under $WIN/DriverStore" >&2; exit 1; }
[ -s "$pkg/json.lst" ] && [ -s "$pkg/sns_reg_config" ] || { echo "package lacks json.lst or sns_reg_config" >&2; exit 1; }

mkdir -p "$OUT/sensors/config" "$OUT/socinfo"

# 1. config: every file the ADSP can open under \vendor\etc\sensors\config (json.lst entries must exist)
tr -d '\r' <"$pkg/json.lst" | while read -r f; do
	[ -n "$f" ] || continue
	[ -f "$pkg/$f" ] || { echo "json.lst names missing file: $f" >&2; exit 1; }
done
find "$pkg" -maxdepth 1 -type f \( -name '*.json' -o -name '*.bin' -o -name '*.pb' -o -name 'json.lst' \) -exec install -m 0644 {} "$OUT/sensors/config/" \;

# 2. identity files: the Windows package maps these files to \sys\devices\soc0\* (INF lines 553-575), so
#    hexagonrpcd serves <root>/socinfo/ as /sys/devices/soc0 and sns_reg.conf keeps its original paths.
for n in hw_platform soc_id revision platform_subtype platform_subtype_id platform_version; do
	tr -d '\r' <"$pkg/$n" >"$OUT/socinfo/$n"
done
[ -z "$SOC" ] || echo "$SOC" >"$OUT/socinfo/soc_id"
[ -z "$REV" ] || echo "$REV" >"$OUT/socinfo/revision"

# 3. sns_reg.conf: unmodified apart from line endings
tr -d '\r' <"$pkg/sns_reg_config" >"$OUT/sensors/sns_reg.conf"

# 4. registry seed
seeded="none (the ADSP must create the registry; needs the write-capable hexagonrpcd)"
if [ -n "$REG" ]; then
	[ -f "$REG/sns_reg_config" ] || { echo "$REG has no sns_reg_config: not a registry directory" >&2; exit 1; }
	mkdir -p "$OUT/registry-seed"
	cp -a "$REG"/. "$OUT/registry-seed/"
	seeded="copy of $REG"
elif [ "$SEED" = 1 ]; then
	[ -n "$GEN" ] || GEN=$(command -v sscregistrygen || true)
	[ -x "$GEN" ] || { echo "sscregistrygen not found: install the hexagonrpcd RPM or pass --registry-gen (or use --no-seed)" >&2; exit 1; }
	mkdir -p "$OUT/registry-seed"
	hw=$(cat "$OUT/socinfo/hw_platform"); soc=$(cat "$OUT/socinfo/soc_id")
	work=$(mktemp -d)
	trap 'rm -rf "$work"' EXIT
	mkdir "$work/in"
	# One run per file in json.lst order, so groups defined twice resolve the same way on every machine
	# (the tool itself would use readdir order).
	tr -d '\r' <"$pkg/json.lst" | awk 'NF && !seen[$0]++' | while read -r f; do
		rm -f "$work/in"/*
		cp "$pkg/$f" "$work/in/$f"
		"$GEN" -p "$hw" -s "$soc" "$work/in" "$OUT/registry-seed" 2>&1 | sed "s|^|sscregistrygen: |" >&2
	done
	seeded="$(find "$OUT/registry-seed" -type f | wc -l) files from sscregistrygen (hw_platform $hw, soc_id $soc)"
fi

( cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS )
echo "staged $(find "$OUT/sensors/config" -type f | wc -l) config files; identity: $(cat "$OUT/socinfo/hw_platform") soc_id=$(cat "$OUT/socinfo/soc_id") revision=$(cat "$OUT/socinfo/revision")"
echo "registry seed: $seeded"
