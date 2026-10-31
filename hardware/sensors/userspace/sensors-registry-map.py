#!/usr/bin/env python3
"""Map the SSC sensor JSON configuration of the Windows package to registry files.

Read-only analysis. Input: a directory with the JSON files of surfacepro_snscfgcrd8380 and its json.lst.
Output: Markdown on stdout (JSON file -> registry groups -> number of registry files) for one platform
filter, using the same rules as hexagonrpc's tools/sscregistrygen.c (one file per top-level group plus
one per nested key that starts with a dot, recursively).

Usage: sensors-registry-map.py PKGDIR [--platform CRD] [--soc 615]
The output names configuration files and group names only, never values. It is safe for the
evidence notes; the input stays out of git (S5).
"""
import argparse
import json
import os
import sys


def count_files(obj):
    """Registry files created for one group object: itself plus every dotted descendant."""
    n = 1
    for key, val in obj.items():
        if key.startswith('.') and isinstance(val, dict):
            n += count_files(val)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pkg')
    ap.add_argument('--platform', default='CRD')
    ap.add_argument('--soc', default='615')
    args = ap.parse_args()

    order = []
    for line in open(os.path.join(args.pkg, 'json.lst'), encoding='utf-8-sig'):
        name = line.strip()
        if name and name not in order:
            order.append(name)

    rows, skipped, invalid = [], [], []
    seen_groups = {}
    for name in order:
        path = os.path.join(args.pkg, name)
        if not os.path.isfile(path):
            skipped.append((name, 'missing in package'))
            continue
        try:
            with open(path, encoding='utf-8-sig') as fh:
                doc = json.load(fh)
        except ValueError as err:
            invalid.append((name, str(err)))
            continue
        cfg = doc.get('config', {})
        plat, soc = cfg.get('hw_platform'), cfg.get('soc_id')
        if (plat is not None and args.platform not in plat) or (soc is not None and args.soc not in soc):
            skipped.append((name, 'filtered out (hw_platform %s, soc_id %s)' % (plat, soc)))
            continue
        groups = []
        for key, val in doc.items():
            if key == 'config' or not isinstance(val, dict):
                continue
            groups.append((key, val.get('owner', '-'), count_files(val)))
            seen_groups.setdefault(key, []).append(name)
        rows.append((name, groups))

    total = sum(n for _, g in rows for _, _, n in g)
    print('# Registry files derived from the JSON configuration (platform %s, soc_id %s)\n' % (args.platform, args.soc))
    print('| JSON file | group (top-level key) | owner | registry files |')
    print('|:--|:--|:--|--:|')
    for name, groups in rows:
        if not groups:
            print('| `%s` | (no groups) | - | 0 |' % name)
        for key, owner, n in groups:
            print('| `%s` | `%s` | %s | %d |' % (name, key, owner, n))
    print('\nTotal files before overwrites: %d (groups defined twice overwrite each other: %s)' % (
        total, ', '.join(sorted(k for k, v in seen_groups.items() if len(v) > 1)) or 'none'))
    print('\nSkipped: ' + '; '.join('%s (%s)' % s for s in skipped))
    print('Invalid JSON (not parsed by any tool): ' + '; '.join('%s (%s)' % s for s in invalid))
    return 0


if __name__ == '__main__':
    sys.exit(main())
