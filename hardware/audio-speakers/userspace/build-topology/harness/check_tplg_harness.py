#!/usr/bin/env python3
"""Check the console logs of the topology harness (see README in this directory).

  check_tplg_harness.py --log-dir DIR [--ids sp11-ids.m4]

DIR holds q-hbase.log (public topology), q-hcl.log (closed-loop topology), q-hdup.log (duplicate
instance id), q-htrunc.log (truncated file), q-hgate.log (speaker gate with the real wsa884x.c). Exit status 0 only if every expectation holds.
The harness runs the real ASoC topology core and the real sound/soc/qcom/qdsp6/topology.c, then
builds APM_CMD_GRAPH_OPEN with the real audioreach.c; this script decodes those packets.
"""
import argparse
import re
import struct
import sys
from pathlib import Path

PID = {0x08001001: "sub_graph", 0x08001000: "container", 0x08001002: "module_list",
       0x08001003: "module_prop", 0x08001004: "module_conn", 0x08001061: "control_links"}
HDR = 24 + 16  # gpr_hdr + apm_cmd_header


def lines(path, case):
    return [ln for ln in Path(path).read_text(errors="replace").splitlines()]


def parse_log(path, case):
    text = lines(path, case)
    info = {"errors": [], "modules": {}, "pkts": {}, "tplg": None, "card": None, "links": {}}
    pkt = {}
    for ln in text:
        m = re.search(rf"HARNESS {case}: audioreach_tplg_init returned (-?\d+)", ln)
        if m:
            info["tplg"] = int(m.group(1))
        m = re.search(rf"HARNESS {case}: card register returned (-?\d+)", ln)
        if m:
            info["card"] = int(m.group(1))
        m = re.search(rf"HARNESS {case}: GRAPH (\d+) MOD iid 0x([0-9a-f]+) mid 0x([0-9a-f]+) .* dst0 0x([0-9a-f]+) w=(\S+)", ln)
        if m:
            g, iid, mid, dst, w = int(m.group(1)), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16), m.group(5)
            info["modules"].setdefault(g, []).append((iid, mid, dst, w))
        m = re.search(rf"HARNESS {case}: PKT (\d+) ([0-9a-f]+)$", ln)
        if m:
            pkt.setdefault(int(m.group(1)), "")
            pkt[int(m.group(1))] += m.group(2)
        m = re.search(rf"HARNESS {case}: GRAPH (\d+) PKT bytes (\d+) control_links (\d+)", ln)
        if m:
            info["links"][int(m.group(1))] = int(m.group(3))
        if re.search(r"Duplicate|Failed to|Not a valid token|ASoC: failed|could not load|Oops|Kernel panic|invalid component", ln):
            info["errors"].append(ln.strip()[:160])
    info["pkts"] = {g: bytes.fromhex(h) for g, h in pkt.items()}
    return info


def decode(blob):
    off, out = HDR, {}
    while off + 16 <= len(blob):
        iid, pid, size, _ = struct.unpack_from("<4I", blob, off)
        body = blob[off + 16:off + 16 + size]
        off += 16 + ((size + 7) & ~7)
        out[PID.get(pid, hex(pid))] = body
    return out


def words(b):
    return struct.unpack(f"<{len(b) // 4}I", b[: len(b) // 4 * 4])


def module_list(body):
    w, n, i, res = words(body), None, 1, []
    for _ in range(w[0]):
        sg, cont, cnt = w[i:i + 3]
        i += 3
        for _ in range(cnt):
            res.append((sg, cont, w[i], w[i + 1]))  # module id, instance id
            i += 2
    return res


def conns(body):
    w = words(body)
    return [tuple(w[1 + 4 * k:5 + 4 * k]) for k in range(w[0])]


def control_links(body):
    w, res, i = words(body), [], 1
    for _ in range(w[0]):
        p1, port1, p2, port2, nprops = w[i:i + 5]
        prop_id, prop_size, nint = w[i + 5:i + 8]
        res.append((p1, port1, p2, port2, w[i + 8] if nint else None))
        i += 8 + nint
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", type=Path, required=True)
    ap.add_argument("--ids", type=Path, help="private sp11-ids.m4 (instance ids of the Windows graph)")
    args = ap.parse_args()
    ids = {k: int(v, 16) for k, v in re.findall(r"define\(`SP11_(\w+)_IID', `(0x[0-9a-f]+)'", args.ids.read_text())} if args.ids else {}
    ok = True

    def check(cond, what):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + what)
        ok &= bool(cond)

    base = parse_log(args.log_dir / "q-hbase.log", "hbase")
    check(base["tplg"] == 0 and base["card"] == 0 and not base["errors"], "public topology loads with no parser error")
    check(sorted(base["modules"]) == [0, 1, 2, 3, 104, 105, 110, 129], f"public graph ids {sorted(base['modules'])}")

    cl = parse_log(args.log_dir / "q-hcl.log", "hcl")
    check(cl["tplg"] == 0 and cl["card"] == 0 and not cl["errors"], "closed-loop topology loads with no parser error")
    check(sorted(cl["modules"]) == [0, 1, 2, 3, 4, 104, 105, 106, 110, 129], f"closed-loop graph ids {sorted(cl['modules'])}")
    all_iids = [m[0] for g in cl["modules"].values() for m in g]
    check(len(all_iids) == len(set(all_iids)), "module instance ids unique across all graphs")
    if ids:
        sp, vi, log, dma = ids["SP"], ids["VI"], ids["VILOG"], ids["VIDMA"]
        g105 = {m[0]: m for m in cl["modules"].get(105, [])}
        g106 = {m[0]: m for m in cl["modules"].get(106, [])}
        check(sp in g105 and g105[sp][1] == 0x070010E2, f"graph 105 holds SP 0x{sp:x} (module 0x070010e2)")
        check(set(g106) == {vi, log, dma} and g106[vi][1] == 0x070010E3 and g106[dma][1] == 0x07001024,
              "graph 106 is CODEC_DMA_SOURCE -> DATA_LOGGING -> SP_VI with the Windows ids")
        check(g106[vi][2] == 0 and g106[dma][2] == log and g106[log][2] == vi, "graph 106 chain connections, VI has no consumer")
        d105, d106 = decode(cl["pkts"][105]), decode(cl["pkts"][106])
        ml105 = {m[3]: m[2] for m in module_list(d105["module_list"])}
        ml106 = {m[3]: m[2] for m in module_list(d106["module_list"])}
        check(sp in ml105 and ml105[sp] == 0x070010E2, "GRAPH_OPEN 105 module list forwards SP instance id verbatim")
        check(set(ml106) == {vi, log, dma}, "GRAPH_OPEN 106 module list forwards the three instance ids verbatim")
        c106 = [(c[0], c[2]) for c in conns(d106["module_conn"])]
        check(sorted(c106) == sorted([(dma, log), (log, vi)]), f"GRAPH_OPEN 106 connections {[(hex(a), hex(b)) for a, b in c106]}")
        cl105 = control_links(d105["control_links"]) if "control_links" in d105 else []
        check(any(l[0] == vi and l[2] == sp for l in cl105), "GRAPH_OPEN 105 carries the VI-SP control link of the sp11cl file")
        check("control_links" not in d106, "GRAPH_OPEN 106 carries no control link (declared once, by the graph of peer 2)")
        check(cl["links"].get(105) == 1 and cl["links"].get(106) == 0, "control link counts 105:1 106:0")

    dup = parse_log(args.log_dir / "q-hdup.log", "hdup")
    check(any("Duplicate Module Instance ID" in e for e in dup["errors"]),
          "negative control: a duplicate module instance id is reported by the real parser")
    print("INFO  duplicate id case: audioreach_tplg_init returned", dup["tplg"], "(the error is logged but not propagated)")
    tr = parse_log(args.log_dir / "q-htrunc.log", "htrunc")
    check(tr["tplg"] not in (0, None), "negative control: a truncated file is rejected")

    gate = (args.log_dir / "q-hgate.log").read_text(errors="replace") if (args.log_dir / "q-hgate.log").exists() else ""
    gl = re.findall(r"GATE (PASS|FAIL): (.*)", gate)
    for verdict, what in gl:
        check(verdict == "PASS", "gate: " + what)
    check(len(gl) >= 25 and "HARNESS DONE" in gate, f"gate case ran to the end ({len(gl)} checks)")
    check(not re.search(r"Oops|Kernel panic|BUG:|WARNING:", gate), "gate case: no oops, BUG or WARNING")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
