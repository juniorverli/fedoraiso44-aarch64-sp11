#!/usr/bin/env bash
# Build M14 DTB variants from the release series without git writes.
# scripts/kernel-dtb-m14.sh [--preflight] [KVER]; publication requires checked revision-11 RPMs.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"
preflight=0
if [[ ${1:-} == --preflight ]]; then preflight=1; shift; fi
kver=${1:-$KERNEL_KVER}
[[ $KERNEL_SERIES_REV == 11 && $kver == "$KERNEL_KVER" ]] || die "M14 requires series_rev 11 and $KERNEL_KVER"
kernel_series_check
src="$SP11_OUT/linux/m14"
checks="$SP11_OUT/build/dtb-m14-checks"
stage="$checks/variants"
outdir="$SP11_OUT/dtb-variants/$kver/qcom"
packaged="$KERNEL_BUILD_DIR/check/root/lib/modules/$kver/dtb/qcom/x1p64100-microsoft-denali.dtb"
record="$KERNEL_RPMS_DIR/kernel-$kver.json"
if ((preflight)); then
  # Run the same DT gates before an expensive RPM build; publish no artifacts.
  packaged=""
else
  [[ -f $packaged && -f $record ]] || die "run the revision-11 release build and kernel-check first"
fi
mkdir -p "$checks" "$outdir" "$SP11_OUT/linux"
exec 8>"$SP11_OUT/.kernel-m14.lock"
flock -w 14400 8 || die "no M14 source lock after 4 h"
kernel_guard_start dev
if [[ -e $src ]]; then
  [[ ! -e $src/.git && -f $src/.kernel-dtb-m14 ]] || die "refusing to replace a source tree not owned by this script: $src"
  rm -rf -- "$src"
fi
mkdir "$src"
touch "$src/.kernel-dtb-m14"
base=$(kernel_toml commit)
git -C "$KERNEL_REPO/sources/linux" archive "$base" | tar -x -C "$src"
patches=()
: > "$checks/variant-series-apply.log"
while IFS= read -r p; do
  p="${p%%#*}"; p="${p//[[:space:]]/}"
  [[ -n $p ]] || continue
  patches+=("$p")
  {
    echo "$p"
    patch --batch --fuzz=0 -d "$src" -p1 < "$KERNEL_REPO/$p"
  } | tee -a "$checks/variant-series-apply.log"
done < "$KERNEL_REPO/kernel/series"

mkdir -p "$stage"
cp "$KERNEL_REPO/kernel/dtb-variants/"x1p64100-microsoft-denali-{parity,m12,m14,m14-safe,m14-nosnd,m14-notouch,m14-spk}.dts "$stage/"
m12dir="$SP11_OUT/dtb-variants/7.3.0-65.sp11.9.fc44.aarch64/qcom"
for f in m12 m12-audio; do [[ -f $m12dir/x1p64100-microsoft-denali-$f.dtb ]] || die "missing M12 comparison DTB $f"; done
# Preserve the historical parity source in git. New series already applies it;
# replace only the staging copy before kernel-dev copies sibling DTS files.
cat > "$stage/x1p64100-microsoft-denali-parity.dts" <<'DTS'
// SPDX-License-Identifier: BSD-3-Clause
/* Parity is supplied by the integrated LCD board patch. */
#include "x1p64100-microsoft-denali.dts"
DTS

# Source-form compilation retains symbolic references for an auditable diff.
# Every compiled result must match the kernel build byte for byte.
canonical_source() {
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -e -c '
    src=$1; stage=$2; checks=$3; name=$4
    input="$stage/$name.dts"
    if [ "$name" = x1p64100-microsoft-denali ]; then
      input="$src/arch/arm64/boot/dts/qcom/$name.dts"
    fi
    gcc -E -nostdinc -I "$stage" -I "$src/arch/arm64/boot/dts/qcom" \
      -I "$src/arch/arm64/boot/dts" -I "$src/arch/arm64/boot/dts/include" -I "$src/include" \
      -undef -D__DTS__ -x assembler-with-cpp "$input" -o "$checks/$name.i"
    dtc -I dts -O dts -qq "$checks/$name.i" -o "$checks/$name.source.dts"
    dtc -I dts -O dtb -@ -qq "$checks/$name.i" -o "$checks/$name.source.dtb"
  ' bash "$src" "$stage" "$checks" "$1"
}

# The baseline is the exact packaged DT, not the previous revision or M6.
canonical_source x1p64100-microsoft-denali
[[ -z $packaged ]] || cmp "$checks/x1p64100-microsoft-denali.source.dtb" "$packaged"

# order matters: later variants use earlier source DTBs as baselines.
#   variant       baseline (diff recorded; notouch must change only touch)   M12 DTB it must equal apart from disabled camera nodes
declare -A baseline_of=( [m14-nosnd]="" [m14-safe]="" [m14]=m14-safe [m14-notouch]=m14-safe [m14-spk]="" )
declare -A m12_of=( [m14-nosnd]=m12 [m14-safe]=m12-audio [m14]="" [m14-notouch]="" [m14-spk]="" )
for name in m14-nosnd m14-safe m14 m14-notouch m14-spk; do
  full=x1p64100-microsoft-denali-$name
  rm -f "$SP11_OUT/build/dev-m14/arch/arm64/boot/dts/qcom/$full.dtb"
  "$KERNEL_REPO/scripts/kernel-dev.sh" --check m14 variant "$stage/$full.dts" \
    2>&1 | tee "$checks/$name.build.log"
  canonical_source "$full"
  built="$SP11_OUT/build/dev-m14/arch/arm64/boot/dts/qcom/$full.dtb"
  cmp "$checks/$full.source.dtb" "$built"
  [[ $name != m14-nosnd || -z $packaged ]] || cmp "$built" "$packaged"
  baseline="${packaged:-$checks/x1p64100-microsoft-denali.source.dtb}"
  [[ -z ${baseline_of[$name]} ]] || baseline="$checks/x1p64100-microsoft-denali-${baseline_of[$name]}.source.dtb"
  extra_args=()
  [[ -z ${m12_of[$name]} ]] || extra_args+=(--previous-m12 "$m12dir/x1p64100-microsoft-denali-${m12_of[$name]}.dtb")
  case $name in
    m14-spk) profile=d26 ;;
    *) profile=default ;;
  esac
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -e -c '
    schema=$1; dtb=$2; checks=$3; name=$4; repo=$5; baseline=$6; profile=$7; shift 7
    dt-validate -s "$schema" "$dtb" > "$checks/$name.dt-validate.log" 2>&1
    if [ "$name" = m14-spk ]; then
      # The d26 marker has no binding: accept exactly its schema complaints, nothing else.
      ! grep -v "from schema" "$checks/$name.dt-validate.log" | grep -v "sp11,speaker-policy" | grep -q .
      grep -q "sp11,speaker-policy" "$checks/$name.dt-validate.log"
    else
      test ! -s "$checks/$name.dt-validate.log"
    fi
    dtc -I dtb -O dts -qq "$dtb" -o "$checks/$name.effective.dts"
    python3 -I "$repo/scripts/kernel-dtb-safety.py" "$checks/$name.effective.dts" --profile "$profile" \
      --also=gpu@3d00000 --also=soundwire@6b10000 > "$checks/$name.safety.json"
    python3 -I "$repo/scripts/kernel-m8-check.py" "$dtb" --variant "$name" --cma-dma32 --parity-in-base \
      --baseline "$baseline" "$@" > "$checks/$name.wiring.json"
  ' bash "$SP11_OUT/build/dev-m14/Documentation/devicetree/bindings/processed-schema.json" \
    "$built" "$checks" "$name" "$KERNEL_REPO" "$baseline" "$profile" "${extra_args[@]}"
  # Only m14-spk may pass d26; every other DTB must also be refused by nothing but pass default, and
  # m14-spk must fail the default profile (kernel-m8-check asserts the latter).
  cp "$built" "$checks/$full.built.dtb"
done

if ((preflight)); then echo 'kernel-dtb-m14: preflight PASS (no publication)'; exit 0; fi

python3 -I - "$KERNEL_REPO" "$checks" "$outdir" "$base" "$kver" "$record" "${patches[@]}" <<'PY'
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
import difflib, hashlib, json, re, shutil, sys

repo, checks, outdir = map(Path, sys.argv[1:4])
base, kver, release_path = sys.argv[4:7]
patches = sys.argv[7:]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
release = json.loads(Path(release_path).read_text())
assert release['series_rev'] == 11 and release['build']['rpmbuild_rc'] == 0
assert release['btf']['vmlinux'] == 'ok' and release['btf']['modules_without_btf'] == 0
assert release['btf']['modules_with_btf'] == release['btf']['modules_total'] > 0
assert release['kver'] == kver and release['base']['commit'] == base
manifest = ''.join(f'{p} {sha(repo / p)}\n' for p in patches)
assert release['series_hash_sha256'] == hashlib.sha256(manifest.encode()).hexdigest()
assert release['config']['fragment_check'] == 'ok' and release['dtb_in_kernel_core'] == 'ok'
assert release['dtb_check']['rc'] == '0' and release['dtb_check']['warning_lines'] == 0
assert release['m14']['s1_effective_status']['s1_ok'] and not release['m14']['wiring']['gpu_enabled']
assert release['m14']['cma_dma32']['allocation_end_exclusive'] == 0x100000000
def canonical(name):
    return [line for line in (checks / f'x1p64100-microsoft-denali{name}.source.dts').read_text().splitlines()
            if line.strip() and not re.match(r'\s*phandle = ', line)]
subjects = [str(BytesParser(policy=policy.default).parsebytes((repo / p).read_bytes())['Subject'])
            for p in patches]
D = 'kernel/dtb-variants/x1p64100-microsoft-denali-'
chain = {'m14-nosnd': (D + 'm12.dts', D + 'm14-nosnd.dts'),
         'm14-safe': (D + 'm12.dts', D + 'm14-safe.dts'),
         'm14': (D + 'm12.dts', D + 'm14-safe.dts', D + 'm14.dts'),
         'm14-notouch': (D + 'm12.dts', D + 'm14-safe.dts', D + 'm14-notouch.dts'),
         'm14-spk': (D + 'm12.dts', D + 'm14-spk.dts')}
extra_sources = {'m14-spk': 'hardware/audio-speakers/patches/dtb-variants/x1p64100-microsoft-denali-m13-spk.dts'}
for name, previous in [('m14-nosnd', ''), ('m14-safe', ''), ('m14', '-m14-safe'), ('m14-notouch', '-m14-safe'), ('m14-spk', '')]:
    full = f'x1p64100-microsoft-denali-{name}'
    before, after = canonical(previous), canonical('-' + name)
    diff = list(difflib.unified_diff(before, after, fromfile='packaged' if not previous else previous[1:],
                                     tofile=name, lineterm=''))
    (checks / f'{name}.diff').write_text('\n'.join(diff) + '\n')
    includes = ['kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts'] + list(chain[name])
    profile = 'd26' if name == 'm14-spk' else 'default'
    log = (checks / f'{name}.build.log').read_text()
    timing = re.search(r'kernel-dev: m14 variant .* took (\d+) s', log)
    warnings = len([l for l in log.splitlines() if l.startswith(('arch/arm64/boot/dts/qcom/' + full + '.dtb:', full + '.dtb:'))
                    and 'sp11,speaker-policy' not in l])
    marker_lines = len([l for l in log.splitlines() if 'sp11,speaker-policy' in l])
    assert warnings == 0, f'{name}: CHECK_DTBS diagnostics'
    assert timing and 'CONFIG_DEBUG_INFO_BTF=y' in (repo / 'out/build/dev-m14/.config').read_text()
    assert 'CONFIG_DEBUG_INFO_BTF_MODULES=y' in (repo / 'out/build/dev-m14/.config').read_text()
    dtb = checks / f'{full}.source.dtb'
    record = dict(name=full, kver=kver, series_rev=11, built_utc=datetime.now(timezone.utc).isoformat(),
        base=f'v7.3 {base}', source_commit=base, kernel_tree='out/linux/m14',
        source_mode='git archive; release patches applied by patch --fuzz=0, no commits',
        series_hash_sha256=release['series_hash_sha256'], patches_applied=patches,
        patch_subjects=subjects, patch_sha256={p: sha(repo / p) for p in patches},
        release_record=release_path, release_record_sha256=sha(Path(release_path)),
        build_seconds=int(timing[1]), dt_validate_warning_lines='0',
        checks=dict(dt_validate=dict(exit_code=0, diagnostic_lines=0 if name != 'm14-spk' else 'marker-only (sp11,speaker-policy has no binding)'),
                    check_dtbs=dict(exit_code=0, diagnostic_lines=warnings, marker_only_diagnostic_lines=marker_lines),
                    source_recompiled_dtb_identical=True, packaged_source_recompiled_dtb_identical=True,
                    s1_effective_status=json.loads((checks / f'{name}.safety.json').read_text()),
                    wiring=json.loads((checks / f'{name}.wiring.json').read_text()),
                    diff_vs_base=dict(base='packaged' if not previous else previous[1:], lines=diff),
                    btf_config=True, btf_modules_config=True),
        overlay=f'kernel/dtb-variants/{full}.dts',
        overlay_sha256=sha(repo / f'kernel/dtb-variants/{full}.dts'),
        include_sha256={p: sha(repo / p) for p in includes},
        safety_profile=profile,
        source_in_owner_folder=extra_sources.get(name),
        staging_parity_shim_sha256=sha(checks / 'variants/x1p64100-microsoft-denali-parity.dts'),
        packaged_parity_integrated=True,
        evidence=None, dtb=f'qcom/{full}.dtb', sha256=sha(dtb), boot_menu_entry_requested=True)
    shutil.copyfile(dtb, outdir / f'{full}.dtb')
    (outdir / f'{full}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'kernel-dtb-m14: {outdir / (full + ".dtb")} sha256 {record["sha256"]}')
PY
