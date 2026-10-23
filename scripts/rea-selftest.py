#!/usr/bin/env python3
"""Prove that REA + Ghidra decode every CPU architecture found in the dumps.

For one sample per (container, machine) from sources/binary-catalog.tsv, plus
the named extra samples, run `rea inspect` and `rea decompile` of the entry
point, and count markers of wrong decoding (bad instructions, halt_baddata).
Results go to out/rea-selftest/ (not in git) and a summary table to stdout.

  python3 -I scripts/rea-selftest.py [extra-path ...]
"""
import csv
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REA = os.path.expanduser("~/tools/rea/node_modules/.bin/rea")
OUT = os.path.join(ROOT, "out", "rea-selftest")
ENV = dict(os.environ,
           GHIDRA_INSTALL_DIR=os.path.expanduser("~/tools/ghidra_12.1.4_PUBLIC"),
           JAVA_HOME=os.path.expanduser("~/tools/jdk-21.0.12.1+1"))
BAD = ("halt_baddata", "Bad instruction", "bad instruction", "BADSPACEBASE", "Truncating control flow")


def rea(args, timeout=1800):
    p = subprocess.run([REA] + args + ["--provider", "ghidra", "--format", "json"],
                       capture_output=True, text=True, env=ENV, timeout=timeout)
    try:
        return json.loads(p.stdout), p.stderr
    except ValueError:
        return None, (p.stderr or p.stdout)[-800:]


def samples():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "sources", "binary-catalog.tsv")), delimiter="\t"))
    best = {}
    for r in rows:
        if r["kind"] != "code" or "NO GHIDRA" in r["ghidra_language"]:
            continue
        k = (r["container"].split(" ")[0], r["machine"])
        if k not in best or int(r["size"]) < int(best[k]["size"]):
            best[k] = r
    by_path = {r["path"]: r for r in rows}
    picked = list(best.values())
    for extra in sys.argv[1:]:
        if extra in by_path and by_path[extra] not in picked:
            picked.append(by_path[extra])
    return picked


def main():
    os.makedirs(OUT, exist_ok=True)
    results = []
    for r in samples():
        path = os.path.join(ROOT, "sources", "windows", r["path"])
        name = os.path.basename(path).replace(" ", "_")
        snap = os.path.join(OUT, name + ".snap")
        res = {"file": r["path"], "catalog_machine": r["machine"], "language": r["ghidra_language"]}
        inspect, err = rea(["inspect", path, "--snapshot", snap])
        if not inspect:
            res.update(status="INSPECT-FAILED", note=err.strip().splitlines()[-1] if err.strip() else "")
            results.append(res)
            continue
        json.dump(inspect, open(os.path.join(OUT, name + ".inspect.json"), "w"), indent=1)
        nr = inspect.get("normalized_result") or {}
        res.update(evidence_id=inspect.get("evidence_id"),
                   rea_arch=(inspect.get("subject") or {}).get("architecture"),
                   procedures=nr.get("procedure_count"))
        dec, err = rea(["decompile", path, "entry", "--snapshot", snap])
        text = json.dumps(dec) if dec else (err or "")
        open(os.path.join(OUT, name + ".decompile.json"), "w").write(text)
        bad = sum(text.count(b) for b in BAD)
        lines = text.count("\\n")
        res.update(decompile="ok" if dec else "failed", pseudo_lines=lines, bad_markers=bad,
                   status="OK" if dec and bad == 0 and lines > 3 else ("CHECK" if dec else "DECOMPILE-FAILED"))
        if not dec:
            res["note"] = (err or "").strip().splitlines()[-1][:200] if (err or "").strip() else ""
        results.append(res)
        print(json.dumps(res), flush=True)
    json.dump(results, open(os.path.join(OUT, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
