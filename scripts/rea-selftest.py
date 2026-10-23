#!/usr/bin/env python3
"""Prove that REA + Ghidra decode every CPU architecture found in the dumps.

For one sample per (container, machine) from sources/binary-catalog.tsv, plus
the named extra samples: load it with the Ghidra language of its catalog row
(REA_GHIDRA_LANGUAGE_ID), list its procedures, decompile three real ones
(first, middle, last) and count markers of wrong decoding (bad instructions,
halt_baddata).
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


def rea(args, language=None, timeout=3600):
    env = dict(ENV, GHIDRA_MAXMEM="4G", REA_GHIDRA_STARTUP_TIMEOUT_MS="2400000")
    if language:
        env["REA_GHIDRA_LANGUAGE_ID"] = language  # from the catalog, never guessed
    p = subprocess.run([REA] + args + ["--provider", "ghidra", "--format", "json"],
                       capture_output=True, text=True, env=env, timeout=timeout)
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
        lang = r["ghidra_language"]
        inspect, err = rea(["inspect", path, "--snapshot", snap], lang)
        if not inspect:
            res.update(status="INSPECT-FAILED", note=(err or "").strip()[-300:])
            results.append(res)
            print(json.dumps(res), flush=True)
            continue
        json.dump(inspect, open(os.path.join(OUT, name + ".inspect.json"), "w"), indent=1)
        nr = inspect.get("normalized_result") or {}
        res.update(evidence_id=inspect.get("evidence_id"),
                   rea_arch=(inspect.get("subject") or {}).get("architecture"),
                   procedures=nr.get("procedure_count"))
        found, err = rea(["search", path, ".", "--kind", "procedures", "--mode", "regex",
                          "--snapshot", snap], lang)
        procs = found.get("normalized_result") if isinstance(found, dict) else None
        procs = [x["address"] for x in (procs or []) if not str(x.get("address", "")).startswith("EXTERNAL")]
        if not procs:
            res.update(status="NO-PROCEDURES", note=(err or json.dumps(found))[-300:])
            results.append(res)
            print(json.dumps(res), flush=True)
            continue
        picks = sorted({procs[0], procs[len(procs) // 2], procs[-1]}, key=procs.index)
        checked, bad, lines, failed = [], 0, 0, []
        for addr in picks:
            dec, err = rea(["decompile", path, addr, "--snapshot", snap], lang)
            code = dec.get("normalized_result") if isinstance(dec, dict) else None
            if not isinstance(code, str) or "{" not in code:
                failed.append(addr)
                continue
            open(os.path.join(OUT, f"{name}.{addr.replace(':', '_')}.c"), "w").write(code)
            checked.append(addr)
            bad += sum(code.count(b) for b in BAD)
            lines += code.count("\n")
        res.update(decompiled=checked, failed=failed, pseudo_lines=lines, bad_markers=bad,
                   status="OK" if checked and not failed and bad == 0 else
                          ("BAD-DECODE" if bad else "PARTIAL" if checked else "DECOMPILE-FAILED"))
        results.append(res)
        print(json.dumps(res), flush=True)
    json.dump(results, open(os.path.join(OUT, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
