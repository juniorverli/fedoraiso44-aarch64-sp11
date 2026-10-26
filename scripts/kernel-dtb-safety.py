#!/usr/bin/env python3
"""Effective-status check of a DTB (S1: no speaker may be enabled).

  kernel-dtb-safety.py FILE.dts-from-dtc [--json]

Reads the text `dtc -I dtb -O dts` prints, walks the node tree, and reports every node whose
`compatible` contains one of the watched strings with its own status and its effective status.
A node is effective-enabled only if it and every ancestor has status absent, "okay" or "ok";
a disabled parent bus therefore disables its children. Also reports the effective status of
the nodes named by --also (path suffix match, for example gpu@3d00000).
Exit 0 if no watched node is effectively enabled, 1 otherwise, 2 on usage error.
Owner: kernel worker.
"""
import json, re, sys

WATCH = ("wsa884", "sdw20217020400", "x1e80100-sndcard")   # WSA8845 speakers enumerate as sdw20217020400
args = [a for a in sys.argv[1:] if not a.startswith("--")]
also = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--also=")]
if len(args) != 1:
    print(__doc__); sys.exit(2)

stack = []        # [name, status|None, compatible-list]
nodes = []        # (path, own_status, effective_enabled, compatibles)
open_re = re.compile(r'^\s*(?:[\w$.+-]+:\s*)?([^\s{;=]*)\s*\{\s*$')
for line in open(args[0]):
    m = open_re.match(line)
    if m and not line.strip().startswith(("/*", "*")):
        stack.append([m.group(1) or "/", None, []])
        continue
    s = line.strip()
    if s == "};":
        n = stack.pop()
        path = "/".join(x[0] for x in stack[1:] + [n]) if stack else "/"
        enabled = all(x[1] in (None, "okay", "ok") for x in stack + [n])
        nodes.append(("/" + path.strip("/"), n[1], enabled, n[2]))
        continue
    if stack:
        ms = re.match(r'status = "([^"]*)";', s)
        if ms: stack[-1][1] = ms.group(1)
        mc = re.match(r'compatible = (.*);', s)
        if mc: stack[-1][2] = re.findall(r'"([^"]*)"', mc.group(1))

watched = [n for n in nodes if any(w in c for c in n[3] for w in WATCH)]
report = {
    "watched": [{"path": p, "own_status": st or "(absent=okay)", "effective_enabled": en, "compatible": c}
                for p, st, en, c in watched],
    "also": [{"path": p, "own_status": st or "(absent=okay)", "effective_enabled": en}
             for p, st, en, c in nodes if any(p.endswith("/" + a) or p == a for a in also)],
}
report["s1_ok"] = bool(watched) and not any(n[2] for n in watched)
report["watched_count"] = len(watched)
print(json.dumps(report, indent=1))
sys.exit(0 if report["s1_ok"] else 1)
