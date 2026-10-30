#!/usr/bin/env python3
"""Run strict checkpatch on actual patch input, avoiding tracked-file autodetection."""
from pathlib import Path
import argparse
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
PATCHES = ROOT / 'hardware/touch-pen/patches'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kernel-root', type=Path, default=ROOT / 'out/linux/touch-pen')
parser.add_argument('--output', type=Path, help='directory for raw output and JSON totals')
args = parser.parse_args()
kernel = args.kernel_root.resolve()
failed = 0
records = []
output = []
for name in (PATCHES / 'series').read_text().splitlines():
    name = name.split('#', 1)[0].strip()
    if not name:
        continue
    result = subprocess.run(
        [str(kernel / 'scripts/checkpatch.pl'), '--strict', '--no-signoff',
         '--show-types', '--root=' + str(kernel), '-'],
        input=(PATCHES / name).read_text(), cwd=kernel, capture_output=True, text=True,
        check=False)
    block = name + '\n' + result.stdout + result.stderr
    output.append(block)
    print(block, flush=True)
    totals = re.search(r'total: (\d+) errors, (\d+) warnings, (\d+) checks', result.stdout)
    if result.stderr or not totals or result.returncode not in (0, 1):
        raise RuntimeError(f'checkpatch tool failure for {name}: {block}')
    errors, warnings, checks = map(int, totals.groups())
    records.append(dict(patch=name, returncode=result.returncode,
                        errors=errors, warnings=warnings, checks=checks))
    failed += result.returncode != 0
if args.output:
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'checkpatch.log').write_text('\n'.join(output))
    (args.output / 'checkpatch.json').write_text(json.dumps(records, indent=2) + '\n')
print(f'Patches with findings: {failed}', flush=True)
raise SystemExit(bool(failed))
