#!/usr/bin/env bash
# Build M8 DTB variants from the release series without git writes.
# scripts/kernel-dtb-m8.sh [KVER]; requires the checked revision-5 RPM build.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"
kver=${1:-$KERNEL_KVER}
[[ $KERNEL_SERIES_REV == 5 && $kver == "$KERNEL_KVER" ]] || die "M8 requires series_rev 5 and $KERNEL_KVER"
kernel_series_check
src="$SP11_OUT/linux/m8"
checks="$SP11_OUT/build/dtb-m8-checks"
stage="$checks/variants"
outdir="$SP11_OUT/dtb-variants/$kver/qcom"
packaged="$KERNEL_BUILD_DIR/check/root/lib/modules/$kver/dtb/qcom/x1p64100-microsoft-denali.dtb"
record="$KERNEL_RPMS_DIR/kernel-$kver.json"
[[ -f $packaged && -f $record ]] || die "run the revision-5 release build and kernel-check first"
mkdir -p "$checks" "$outdir" "$SP11_OUT/linux"
exec 8>"$SP11_OUT/.kernel-m8.lock"
flock -w 14400 8 || die "no M8 source lock after 4 h"
kernel_guard_start dev
if [[ -e $src ]]; then
  [[ ! -e $src/.git && -f $src/.kernel-dtb-m8 ]] || die "refusing to replace a source tree not owned by this script: $src"
  rm -rf -- "$src"
fi
mkdir "$src"
touch "$src/.kernel-dtb-m8"
base=$(kernel_toml commit)
git -C "$KERNEL_REPO/sources/linux" archive "$base" | tar -x -C "$src"
patches=()
while IFS= read -r p; do
  p="${p%%#*}"; p="${p//[[:space:]]/}"
  [[ -n $p ]] || continue
  patches+=("$p")
  patch --batch --fuzz=0 -d "$src" -p1 < "$KERNEL_REPO/$p"
done < "$KERNEL_REPO/kernel/series"

mkdir -p "$stage"
cp "$KERNEL_REPO/kernel/dtb-variants/"x1p64100-microsoft-denali-{parity,m8,m8-notouch}.dts "$stage/"

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
cmp "$checks/x1p64100-microsoft-denali.source.dtb" "$packaged"

for name in m8 m8-notouch; do
  full=x1p64100-microsoft-denali-$name
  rm -f "$SP11_OUT/build/dev-m8/arch/arm64/boot/dts/qcom/$full.dtb"
  "$KERNEL_REPO/scripts/kernel-dev.sh" --check m8 variant "$stage/$full.dts" \
    2>&1 | tee "$checks/$name.build.log"
  canonical_source "$full"
  built="$SP11_OUT/build/dev-m8/arch/arm64/boot/dts/qcom/$full.dtb"
  cmp "$checks/$full.source.dtb" "$built"
  baseline="$packaged"
  [[ $name != m8-notouch ]] || baseline="$checks/x1p64100-microsoft-denali-m8.source.dtb"
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -e -c '
    schema=$1; dtb=$2; checks=$3; name=$4; repo=$5; baseline=$6
    dt-validate -s "$schema" "$dtb" > "$checks/$name.dt-validate.log" 2>&1
    test ! -s "$checks/$name.dt-validate.log"
    dtc -I dtb -O dts -qq "$dtb" -o "$checks/$name.effective.dts"
    python3 -I "$repo/scripts/kernel-dtb-safety.py" "$checks/$name.effective.dts" \
      --also=gpu@3d00000 --also=soundwire@6b10000 > "$checks/$name.safety.json"
    python3 -I "$repo/scripts/kernel-m8-check.py" "$dtb" --variant "$name" \
      --baseline "$baseline" > "$checks/$name.wiring.json"
  ' bash "$SP11_OUT/build/dev-m8/Documentation/devicetree/bindings/processed-schema.json" \
    "$built" "$checks" "$name" "$KERNEL_REPO" "$baseline"
done

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
assert release['series_rev'] == 5 and release['build']['rpmbuild_rc'] == 0
assert release['btf']['vmlinux'] == 'ok' and release['btf']['modules_without_btf'] == 0
assert release['btf']['modules_with_btf'] == release['btf']['modules_total'] > 0
assert release['kver'] == kver and release['base']['commit'] == base
manifest = ''.join(f'{p} {sha(repo / p)}\n' for p in patches)
assert release['series_hash_sha256'] == hashlib.sha256(manifest.encode()).hexdigest()
assert release['config']['fragment_check'] == 'ok' and release['dtb_in_kernel_core'] == 'ok'
assert release['dtb_check']['rc'] == '0' and release['dtb_check']['warning_lines'] == 0
assert release['m8']['s1_effective_status']['s1_ok'] and not release['m8']['wiring']['gpu_enabled']
def canonical(name):
    return [line for line in (checks / f'x1p64100-microsoft-denali{name}.source.dts').read_text().splitlines()
            if line.strip() and not re.match(r'\s*phandle = ', line)]
subjects = [str(BytesParser(policy=policy.default).parsebytes((repo / p).read_bytes())['Subject'])
            for p in patches]
for name, previous in [('m8', ''), ('m8-notouch', '-m8')]:
    full = f'x1p64100-microsoft-denali-{name}'
    before, after = canonical(previous), canonical('-' + name)
    diff = list(difflib.unified_diff(before, after, fromfile='packaged' if not previous else previous[1:],
                                     tofile=name, lineterm=''))
    (checks / f'{name}.diff').write_text('\n'.join(diff) + '\n')
    includes = ['kernel/dtb-variants/x1p64100-microsoft-denali-parity.dts',
                'kernel/dtb-variants/x1p64100-microsoft-denali-m8.dts']
    if name == 'm8-notouch':
        includes += ['kernel/dtb-variants/x1p64100-microsoft-denali-m8-notouch.dts']
    log = (checks / f'{name}.build.log').read_text()
    timing = re.search(r'kernel-dev: m8 variant .* took (\d+) s', log)
    assert timing and 'CONFIG_DEBUG_INFO_BTF=y' in (repo / 'out/build/dev-m8/.config').read_text()
    assert 'CONFIG_DEBUG_INFO_BTF_MODULES=y' in (repo / 'out/build/dev-m8/.config').read_text()
    dtb = checks / f'{full}.source.dtb'
    record = dict(name=full, kver=kver, series_rev=5, built_utc=datetime.now(timezone.utc).isoformat(),
        base=f'v7.3 {base}', source_commit=base, kernel_tree='out/linux/m8',
        source_mode='git archive; release patches applied by patch --fuzz=0, no commits',
        series_hash_sha256=release['series_hash_sha256'], patches_applied=patches,
        patch_subjects=subjects, patch_sha256={p: sha(repo / p) for p in patches},
        release_record=release_path, release_record_sha256=sha(Path(release_path)),
        build_seconds=int(timing[1]), dt_validate_warning_lines='0',
        checks=dict(dt_validate=dict(exit_code=0, diagnostic_lines=0),
                    source_recompiled_dtb_identical=True, packaged_source_recompiled_dtb_identical=True,
                    s1_effective_status=json.loads((checks / f'{name}.safety.json').read_text()),
                    wiring=json.loads((checks / f'{name}.wiring.json').read_text()),
                    diff_vs_base=dict(base='packaged' if not previous else previous[1:], lines=diff),
                    btf_config=True, btf_modules_config=True),
        overlay=f'kernel/dtb-variants/{full}.dts',
        overlay_sha256=sha(repo / f'kernel/dtb-variants/{full}.dts'),
        include_sha256={p: sha(repo / p) for p in includes},
        evidence=None, dtb=f'qcom/{full}.dtb', sha256=sha(dtb), boot_menu_entry_requested=True)
    shutil.copyfile(dtb, outdir / f'{full}.dtb')
    (outdir / f'{full}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'kernel-dtb-m8: {outdir / (full + ".dtb")} sha256 {record["sha256"]}')
PY
