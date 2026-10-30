#!/usr/bin/env python3
"""Check effective speaker status in dtc-decompiled DTS (S1).

An enabled x1e80100 card is allowed only with no WSA link and an effectively
disabled swr0. All WSA884x amplifiers must remain effectively disabled.

Profiles (D26, plan/decisions.md): "default" (packaged DTB and every normal
entry) never accepts an enabled speaker path and rejects the marker. "d26"
accepts an enabled speaker path only when /chosen has
sp11,speaker-policy = "d26-open-loop-v1"; the paths are then listed in
d26_speaker_paths. The marker is a tooling contract, not protection evidence.
Usage: kernel-dtb-safety.py FILE [--json] [--also=PATH-SUFFIX] [--profile default|d26]
Owner: kernel worker.
"""
import argparse
import json
from pathlib import Path
import re

WATCH = ('wsa884', 'sdw20217020400', 'x1e80100-sndcard')
MARKER = '"d26-open-loop-v1"'


def check(source, also=(), profile='default'):
    nodes, stack = {}, []
    for line in source.splitlines():
        s = line.strip()
        match = re.match(r'^(?:[\w$.+-]+:\s*)?([^\s{;=]*)\s*\{$', s)
        if match and not s.startswith(('/*', '*')):
            name = match[1] or '/'
            path = stack[-1].rstrip('/') + '/' + name if stack else '/'
            if path in nodes:
                raise ValueError(f'Duplicate node: {path}')
            nodes[path] = {}
            stack.append(path)
        elif s == '};':
            stack.pop()
        elif stack and s.endswith(';'):
            key, sep, value = s[:-1].partition(' = ')
            nodes[stack[-1]][key] = value if sep else ''
    if stack or '/' not in nodes:
        raise ValueError('Incomplete DT tree')

    def enabled(path):
        while True:
            if nodes[path].get('status', '"okay"') not in ('"okay"', '"ok"'):
                return False
            if path == '/':
                return True
            path = path.rsplit('/', 1)[0] or '/'

    def compatibles(path):
        return re.findall(r'"([^"]*)"', nodes[path].get('compatible', ''))

    def report_node(path):
        status = nodes[path].get('status')
        return dict(path=path, own_status=status.strip('"') if status else '(absent=okay)',
                    effective_enabled=enabled(path))

    # Symbols are present in our DTBs. Accept an unambiguous physical path too,
    # so decompiled fixtures and DTBs without symbols can still be checked.
    swr = nodes.get('/__symbols__', {}).get('swr0', '').strip('"')
    candidates = [p for p in nodes if p.endswith('/soundwire@6b10000')]
    if not swr and len(candidates) == 1:
        swr = candidates[0]
    swr_off = swr in nodes and not enabled(swr)
    watched, failures, microphones = [], [], []
    for path in nodes:
        cs = compatibles(path)
        if not any(w in c for c in cs for w in WATCH):
            continue
        item = report_node(path)
        item['compatible'] = cs
        watched.append(item)
        if not enabled(path):
            continue
        card = any('x1e80100-sndcard' in c for c in cs)
        amplifier = any(w in c for c in cs for w in WATCH[:2])
        links = [p for p in nodes if p.startswith(path + '/')
                 and ('wsa' in p.rsplit('/', 1)[-1].lower()
                      or 'wsa' in nodes[p].get('link-name', '').lower())]
        if card and not amplifier and not links and swr_off:
            microphones.append(path)
        else:
            failures.append(path)
    marker = nodes.get('/chosen', {}).get('sp11,speaker-policy')
    d26_paths = []
    if marker is not None and profile != 'd26':
        failures.append('/chosen/sp11,speaker-policy (marker not allowed in profile %s)' % profile)
    elif failures and profile == 'd26' and marker == MARKER:
        d26_paths, failures = failures, []
    elif marker is not None and marker != MARKER:
        failures.append('/chosen/sp11,speaker-policy (unknown value)')
    return dict(profile=profile, speaker_marker=marker, d26_speaker_paths=d26_paths,
                watched=watched, watched_count=len(watched),
                also=[report_node(p) for p in nodes
                      if any(p.endswith('/' + a) or p == a for a in also)],
                microphone_only_cards=microphones, swr0_effectively_disabled=swr_off,
                s1_failures=failures, s1_ok=bool(watched) and not failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dts', type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--also', action='append', default=[])
    parser.add_argument('--profile', choices=('default', 'd26'), default='default')
    args = parser.parse_args()
    result = check(args.dts.read_text(), args.also, args.profile)
    print(json.dumps(result, indent=1))
    return 0 if result['s1_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
