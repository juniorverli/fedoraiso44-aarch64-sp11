#!/usr/bin/env bash
# M6 DT-only build and checks. No git writes, RPM build, or series/config change.
# scripts/kernel-dtb-m6.sh [KVER]; also called by kernel-dtb-variants.sh.
# The disposable dev source is a git archive of the pinned base, with five
# patches applied by patch(1). Its source_commit is the base, not a new commit.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/kernel-common.sh"
kver=${1:-$KERNEL_KVER}
[[ $kver == 7.3.0-65.sp11.3.fc44.aarch64 && $KERNEL_SERIES_REV == 3 ]] || die "M6 requires the unchanged M3 kver / series_rev 3"
kernel_series_check
src="$SP11_OUT/linux/m6"
checks="$SP11_OUT/build/dtb-m6-checks"
outdir="$SP11_OUT/dtb-variants/$kver/qcom"
variants="$KERNEL_REPO/kernel/dtb-variants"
base=$(kernel_toml commit)
patches=(
  hardware/display-lcd/patches/0001-drm-panel-edp-add-LGD-077b.patch
  hardware/display-lcd/patches/0002-arm64-dts-qcom-denali-mux-edp-hpd.patch
  hardware/display-lcd/patches/0003-arm64-dts-qcom-denali-lcd-backlight.patch
  hardware/wifi/patches/0001-arm64-dts-qcom-denali-wire-pcie4-perst-wake.patch
  hardware/usb-typec/patches/0001-arm64-dts-qcom-x1-microsoft-denali-add-the-second-re.patch
)
mkdir -p "$checks" "$outdir" "$SP11_OUT/linux"
# Serialize source preparation too; kernel-dev.sh takes the required build lock.
exec 8>"$SP11_OUT/.kernel-m6.lock"
flock -w 14400 8 || die "no M6 source lock after 4 h"
kernel_guard_start dev
if [[ -e $src ]]; then
  [[ ! -e $src/.git && -f $src/.kernel-dtb-m6 ]] || die "refusing to replace a source tree not owned by this script: $src"
  rm -rf -- "$src"
fi
mkdir "$src"
touch "$src/.kernel-dtb-m6"
git -C "$KERNEL_REPO/sources/linux" archive "$base" | tar -x -C "$src"
for p in "${patches[@]:0:3}"; do
  patch --batch --fuzz=0 -d "$src" -p1 < "$KERNEL_REPO/$p"
done

# Keep labels in the dtc source diff: generated numeric phandles can move when
# the USB-C pin state is added. Recompile that source with -@ as well, and require
# byte equality with the corresponding built DTB before accepting the diff.
canonical_source() {
  local name=$1
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -e -c '
    src=$1; variants=$2; checks=$3; name=$4
    gcc -E -nostdinc -I "$variants" -I "$src/arch/arm64/boot/dts/qcom" \
      -I "$src/arch/arm64/boot/dts" -I "$src/arch/arm64/boot/dts/include" -I "$src/include" \
      -undef -D__DTS__ -x assembler-with-cpp "$variants/x1p64100-microsoft-denali-$name.dts" \
      -o "$checks/$name.i"
    dtc -I dts -O dts -qq "$checks/$name.i" -o "$checks/$name.source.dts"
    dtc -I dts -O dtb -@ -qq "$checks/$name.i" -o "$checks/$name.source.dtb"
  ' bash "$src" "$variants" "$checks" "$name"
}
canonical_source m5
canonical_source m5gpu
cmp "$checks/m5.source.dtb" "$outdir/x1p64100-microsoft-denali-m5.dtb"
cmp "$checks/m5gpu.source.dtb" "$outdir/x1p64100-microsoft-denali-m5gpu.dtb"
for p in "${patches[@]:3}"; do
  patch --batch --fuzz=0 -d "$src" -p1 < "$KERNEL_REPO/$p"
done

for name in m6 m6gpu; do
  full=x1p64100-microsoft-denali-$name
  # Force CHECK_DTBS to run even on a repeated invocation; no kernel is compiled.
  rm -f "$SP11_OUT/build/dev-m6/arch/arm64/boot/dts/qcom/$full.dtb"
  "$KERNEL_REPO/scripts/kernel-dev.sh" --check m6 variant "$variants/$full.dts" \
    2>&1 | tee "$checks/$name.build.log"
  canonical_source "$name"
  built="$SP11_OUT/build/dev-m6/arch/arm64/boot/dts/qcom/$full.dtb"
  cmp "$checks/$name.source.dtb" "$built"
  "$KERNEL_REPO/scripts/kernel-container.sh" run bash -e -c '
    schema=$1; dtb=$2; checks=$3; name=$4; repo=$5
    dt-validate -s "$schema" "$dtb" > "$checks/$name.dt-validate.log" 2>&1
    test ! -s "$checks/$name.dt-validate.log"
    dtc -I dtb -O dts -qq "$dtb" -o "$checks/$name.effective.dts"
    python3 -I "$repo/scripts/kernel-dtb-safety.py" "$checks/$name.effective.dts" \
      --also=gpu@3d00000 --also=soundwire@6b10000 > "$checks/$name.safety.json"
  ' bash "$SP11_OUT/build/dev-m6/Documentation/devicetree/bindings/processed-schema.json" \
    "$built" "$checks" "$name" "$KERNEL_REPO"
done

# Check the complete normalized diff, GPU state and S1 before publishing either
# artifact. Records retain the existing variant fields and add patch/include hashes.
python3 -I - "$KERNEL_REPO" "$checks" "$outdir" "$base" "$kver" "${patches[@]}" <<'PY'
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path
import difflib, hashlib, json, re, shutil, sys

repo, checks, outdir = map(Path, sys.argv[1:4])
base, kver = sys.argv[4:6]
patches = sys.argv[6:]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def normalized(name):
    return [line for line in (checks / f'{name}.source.dts').read_text().splitlines()
            if line.strip() and not re.match(r'\s*phandle = ', line)]

expected = Counter([
    'pinctrl-0 = <&rtmr1_default>;', 'pinctrl-names = "default";',
    'pinctrl-0 = <&pcie4_default>;', 'pinctrl-names = "default";',
    'reset-gpios = <&tlmm 0x92 0x01>;', 'wake-gpios = <&tlmm 0x94 0x01>;',
    'rtmr1_default: rtmr1-reset-n-active-state {', 'pins = "gpio176";',
    'function = "gpio";', 'drive-strength = <0x02>;', 'bias-disable;', '};',
])
subjects = [str(BytesParser(policy=policy.default).parsebytes((repo / p).read_bytes())['Subject'])
            .removeprefix('[PATCH] ') for p in patches]
records = []
for name, previous, gpu_on in [('m6', 'm5', False), ('m6gpu', 'm5gpu', True)]:
    before, after = normalized(previous), normalized(name)
    changes = list(difflib.ndiff(before, after))
    removed = [line for line in changes if line.startswith('- ')]
    added = Counter(line[2:].strip() for line in changes if line.startswith('+ '))
    if removed or added != expected:
        raise SystemExit(f'{name}: unexpected changes against {previous}: removed={removed}, added={added}')
    diff = list(difflib.unified_diff(before, after, fromfile=previous, tofile=name, lineterm=''))
    (checks / f'{name}-vs-{previous}.diff').write_text('\n'.join(diff) + '\n')
    safety = json.loads((checks / f'{name}.safety.json').read_text())
    watched = safety['watched']
    also = {n['path'].rsplit('/', 1)[-1]: n for n in safety['also']}
    if not (safety['s1_ok'] and safety['watched_count'] == 3
            and all(not n['effective_enabled'] for n in watched)
            and next(n for n in watched if n['path'] == '/sound')['own_status'] == 'disabled'
            and also['soundwire@6b10000']['own_status'] == 'disabled'
            and also['gpu@3d00000']['effective_enabled'] == gpu_on):
        raise SystemExit(f'{name}: unexpected S1 or GPU status')
    full = f'x1p64100-microsoft-denali-{name}'
    include_names = ['parity', 'm5', 'm6'] + (['m6gpu'] if gpu_on else [])
    includes = [f'kernel/dtb-variants/x1p64100-microsoft-denali-{n}.dts' for n in include_names]
    dtb = checks / f'{name}.source.dtb'
    record = dict(
        name=full, kver=kver, base=f'v7.3 {base}', series_rev=3,
        kernel_tree='out/linux/m6', source_commit=base,
        source_mode='git archive of source_commit; all patches_applied applied without commits',
        patches_applied=patches, patch_subjects=subjects,
        patch_sha256={p: sha(repo / p) for p in patches},
        dt_validate_warning_lines='0',
        checks=dict(diff_vs_base=dict(base=f'x1p64100-microsoft-denali-{previous}.dtb',
                                     sha256=sha(outdir / f'x1p64100-microsoft-denali-{previous}.dtb'),
                                     method='cpp + dtc -I dts -O dts; numeric phandle properties omitted; source recompilation byte-identical to both DTBs',
                                     only_wifi_and_usb_typec=True, source_recompiled_dtbs_identical=True, lines=diff),
                    dt_validate=dict(exit_code=0, diagnostic_lines=0),
                    s1_effective_status=safety, s1_exit_code=0, gpu_enabled=gpu_on),
        overlay=includes[-1], overlay_sha256=sha(repo / includes[-1]),
        include_sha256={p: sha(repo / p) for p in includes},
        evidence=None, dtb=f'qcom/{full}.dtb', sha256=sha(dtb),
        boot_menu_entry_requested=False if gpu_on else True)
    records.append((full, dtb, record))
for full, dtb, record in records:
    shutil.copyfile(dtb, outdir / f'{full}.dtb')
    (outdir / f'{full}.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f'kernel-dtb-m6: {outdir / (full + ".dtb")} sha256 {record["sha256"]}')
PY
