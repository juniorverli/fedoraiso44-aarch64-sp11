#!/usr/bin/env python3
"""Run strict checkpatch on actual patch input, avoiding tracked-file autodetection."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / 'out/linux/touch-pen'
PATCHES = ROOT / 'hardware/touch-pen/patches'
failed = 0
for name in (PATCHES / 'series').read_text().splitlines():
    name = name.split('#', 1)[0].strip()
    if not name:
        continue
    result = subprocess.run(
        [str(KERNEL / 'scripts/checkpatch.pl'), '--strict', '--no-signoff',
         '--root=' + str(KERNEL), '-'],
        input=(PATCHES / name).read_text(), cwd=KERNEL, capture_output=True, text=True,
        check=False)
    print(name, flush=True)
    print(result.stdout + result.stderr, flush=True)
    failed += result.returncode != 0
print(f'Patches with findings: {failed}', flush=True)
raise SystemExit(bool(failed))
