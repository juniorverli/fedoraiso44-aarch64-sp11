#!/usr/bin/env python3
"""Classify the CHECK_DTBS / dt-validate diagnostics of the m15-spectra DTB.

usage: kernel-dtb-spectra-lines.py SPECTRA_DTB BASELINE_DTB LOG [LOG...]

Only the m15-spectra variant may carry diagnostics: Qualcomm's downstream qcom,cam-* nodes have no binding.
A diagnostic line is accepted only if (a) its subject is a node that exists in SPECTRA_DTB and not in
BASELINE_DTB (the m15-safe DTB), i.e. a node added by hamoa-camera.dtsi, or the existing parent (soc@0,
simple-bus) complaining about a child that is such a node, and (b) its message belongs to one of the classes below.
Any other line, in particular one about a node of the board, is an error (exit 1).

Classes:
  no-schema            failed to match any schema with compatible: [...]
  untyped-property     <prop>: b'...' is not of type ...      (vendor property without schema, raw bytes)
  required-property    '<ranges|#address-cells|#size-cells>' is a required property (Qualcomm node used as a bus)
  nodename             $nodename:0: '<name>' does not match ...   (qcom,cci* are compatible simple-bus)
  compatible           compatible: [...] does not contain items matching the given schema
  unevaluated          Unevaluated properties are not allowed (...)  (the TLMM node lists Qualcomm's pin-state children; each listed name must be added by the dtsi)
Prints JSON with the per-class counts to stdout.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


def paths(dtb):
    text = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-qq', dtb], check=True,
                          capture_output=True, text=True).stdout
    out, stack = set(), []
    for line in text.splitlines():
        line = line.strip()
        if line.endswith(' {'):
            name = line[:-2].strip().split(': ')[-1]
            stack.append(name)
            out.add('/' + '/'.join(stack[1:]) if len(stack) > 1 else '/')
        elif line == '};':
            stack.pop()
    return out


def main():
    dtb, base, logs = sys.argv[1], sys.argv[2], sys.argv[3:]
    added = paths(dtb) - paths(base)
    names = {p.rsplit('/', 1)[-1] for p in added}
    classes = Counter()
    bad = []
    seen = set()
    for log in logs:
        for raw in Path(log).read_text(errors='replace').splitlines():
            m = re.match(r'^(?:\S*/)?x1p64100-microsoft-denali-m15-spectra\.dtb: (.*)$', raw)
            if not m:
                continue
            line = m.group(1)
            if (log, line) in seen:
                continue
            seen.add((log, line))
            if line.startswith('/'):
                node, _, msg = line.partition(': ')
                ok = node in added
                cls = 'no-schema' if msg.startswith('failed to match any schema with compatible:') else None
            else:
                node, _, msg = line.partition(': ')
                subject = re.sub(r' \(.*\)$', '', node)
                child, _, rest = msg.partition(': ')
                if subject in names:
                    ok = True
                elif subject == 'soc@0' and child in names:
                    ok = True        # the bus complains about a Qualcomm child
                elif subject == 'pinctrl@f100000' and msg.startswith('Unevaluated properties are not allowed ('):
                    # every rejected property must be a pin-state node added by Qualcomm's DT
                    listed = re.findall(r"'([^']+)'", msg.split('(', 1)[1])
                    ok = bool(listed) and all(n in names for n in listed)
                else:
                    ok = False
                if 'is not of type' in msg and re.search(r"b'", msg):
                    cls = 'untyped-property'
                elif re.search(r"^'(ranges|#address-cells|#size-cells)' is a required property$", rest or msg) \
                        or re.search(r"^'(ranges|#address-cells|#size-cells)' is a required property$", msg):
                    cls = 'required-property'
                elif msg.startswith('$nodename:0:'):
                    cls = 'nodename'
                elif msg.startswith('compatible:') and 'does not contain items matching' in msg:
                    cls = 'compatible'
                elif 'Unevaluated properties are not allowed' in msg:
                    cls = 'unevaluated'
            if not ok or cls is None:
                bad.append(raw)
            else:
                classes[cls] += 1
    print(json.dumps(dict(accepted_lines=sum(classes.values()), classes=dict(classes),
                          qualcomm_nodes_added=len(added), unaccepted_lines=len(bad)), indent=2))
    if bad:
        print('UNACCEPTED diagnostics (first 20):', file=sys.stderr)
        for b in bad[:20]:
            print('  ' + b[:300], file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
