#!/bin/bash
# Stage the SSC sensor configuration for hexagonrpcd from the operator's own Windows driver dump.
# PRIVATE only (S5): the output is Windows/Qualcomm material. Run it on the build host, write into out/ (not git),
# and let the --private image stage copy the tree to /usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11/sensors.
# Usage: sp11-sensors-stage.sh --windows DIR --out DIR [--registry-from DIR]
#   --windows        sources/windows (contains DriverStore/)
#   --out            empty or new output directory (refused inside a git work tree outside out/)
#   --registry-from  optional pre-parsed Windows registry (DriverData\Qualcomm\fastRPC\persist\sensors\registry\registry)
set -euo pipefail
WIN=""; OUT=""; REG=""
while [ $# -gt 0 ]; do
	case "$1" in
	--windows) WIN=${2:?}; shift ;;
	--out) OUT=${2:?}; shift ;;
	--registry-from) REG=${2:?}; shift ;;
	*) sed -n '2,9p' "$0" >&2; exit 2 ;;
	esac
	shift
done
[ -n "$WIN" ] && [ -n "$OUT" ] || { sed -n '2,9p' "$0" >&2; exit 2; }
case "$(readlink -f "$OUT")" in */out/*|/tmp/*|/var/tmp/*) ;; *) echo "refusing: --out must be under an out/ directory or /tmp" >&2; exit 1 ;; esac

pkg=$(ls -d "$WIN"/DriverStore/surfacepro_snscfgcrd8380.inf_arm64_* 2>/dev/null | grep -v '\.ini$' | head -n1)
[ -d "$pkg" ] || { echo "surfacepro_snscfgcrd8380 package not found under $WIN/DriverStore" >&2; exit 1; }
[ -s "$pkg/json.lst" ] && [ -s "$pkg/sns_reg_config" ] || { echo "package lacks json.lst or sns_reg_config" >&2; exit 1; }

mkdir -p "$OUT/config" "$OUT/registry"
# 1. every file the ADSP can open under \vendor\etc\sensors\config (live registry mapping list: sources/windows/live-inventory/sensors/registry-MSHW048A.txt)
while read -r f; do
	f=${f%$'\r'}; [ -n "$f" ] || continue
	[ -f "$pkg/$f" ] || { echo "json.lst names missing file: $f" >&2; exit 1; }
done <"$pkg/json.lst"
find "$pkg" -maxdepth 1 -type f \( -name '*.json' -o -name '*.bin' -o -name '*.pb' -o -name 'json.lst' \) -exec install -m 0644 {} "$OUT/config/" \;

# 2. platform identity: the files Windows maps to \sys\devices\soc0\* are static files in the package
plat="$OUT/platform"; mkdir -p "$plat"
for n in hw_platform soc_id revision platform_subtype platform_subtype_id platform_version; do
	tr -d '\r' <"$pkg/$n" >"$plat/$n"
done

# 3. sns_reg.conf: the package's sns_reg_config with the soc0 sources pointed at /run/sensors-platform
#    (same layout the reference uses; hexagonrpcd serves these paths to the ADSP)
sed -e 's|\r$||' -e 's|=/sys/devices/soc0/|=/run/sensors-platform/|' "$pkg/sns_reg_config" >"$OUT/sns_reg.conf"

# 4. registry: optional pre-parsed set; otherwise left empty for the ADSP to create (Unknown: see evidence)
if [ -n "$REG" ]; then
	[ -f "$REG/sns_reg_config" ] || { echo "$REG has no sns_reg_config: not a registry directory" >&2; exit 1; }
	cp -a "$REG"/. "$OUT/registry/"
fi

( cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS )
echo "staged $(find "$OUT/config" -type f | wc -l) config files, platform: $(tr '\n' ' ' <"$plat/hw_platform")soc_id=$(cat "$plat/soc_id") rev=$(cat "$plat/revision")"
echo "registry: $( [ -n "$REG" ] && echo "pre-parsed copy" || echo "empty (ADSP must generate it)")"
