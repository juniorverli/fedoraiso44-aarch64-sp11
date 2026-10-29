#!/usr/bin/env python3
"""Reapply the integration and touch series to sparse v7.3 source copies."""
from pathlib import Path
import hashlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'out/agents/touch-ref'
TREE = OUT / 'apply-check'
KERNEL = ROOT / 'out/linux/touch-pen'


def entries(path):
    return [line.split('#', 1)[0].strip() for line in path.read_text().splitlines()
            if line.split('#', 1)[0].strip()]


patches = [ROOT / name for name in entries(ROOT / 'kernel/series')]
patches += [ROOT / 'hardware/touch-pen/patches' / name
            for name in entries(ROOT / 'hardware/touch-pen/patches/series')]
paths = sorted({name for patch in patches for name in
                re.findall(r'^diff --git a/(.*?) b/', patch.read_text(), re.M)})
if TREE.exists():
    shutil.rmtree(TREE)
TREE.mkdir(parents=True)
for name in paths:
    source = ROOT / 'sources/linux' / name
    if source.is_file():
        target = TREE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
log = []
for patch in patches:
    result = subprocess.run(
        ['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch', '-p1', '-i', str(patch)],
        cwd=TREE, text=True, capture_output=True, check=False)
    log.append(str(patch.relative_to(ROOT)) + '\n' + result.stdout + result.stderr)
    (OUT / 'series-apply.log').write_text('\n'.join(log))
    if result.returncode or ('hardware/touch-pen/patches' in str(patch) and
                             re.search(r'offset|fuzz|FAILED', result.stdout)):
        raise RuntimeError(log[-1])
for name in paths:
    assert (TREE / name).read_bytes() == (KERNEL / name).read_bytes(), name
manifest = [f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT)}'
            for p in patches]
(OUT / 'series.sha256').write_text('\n'.join(manifest) + '\n')
print(f'{len(patches)} patches applied; touch series has zero fuzz/offsets; '
      f'{len(paths)} final source files match')
