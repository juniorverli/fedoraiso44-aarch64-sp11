#!/usr/bin/env python3
"""Enumerate the AudioReach use cases of the pinned REV_0D ACDB as DATA.

Structure and sizes only: module ids, instance ids, parameter ids and payload sizes.
No calibration value is printed or written by this tool (S5). The JSON it writes is
still derived from Windows data, so it goes to private out/ only (never git).

Reuses the container decoder of hardware/audio-speakers/userspace/acdb_inspect.py
(read only; this tool adds nothing there). Unlike that tool it does not stop at the
speaker graph: it walks every graph key vector (GKVL) and every calibration row (CDLU).

  acdb_usecases.py ACDB --adsp qcadsp8380.mbn --out out/audio-mics/acdb-usecases.json
  acdb_usecases.py ACDB --summary          (human summary on stdout, ids and sizes only)
"""

import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "audio-speakers" / "userspace"))
import acdb_inspect as ai  # noqa: E402

ADSP_SHA256 = "921870a839ee2aba647b04598d62ed96f3d2d5dfbb2499fc842f9a6ff0e0da13"

# class: Q quality-defining signal processing, P plumbing (format, routing, endpoints),
#        S protection/safety, M metering/logging/control
# handler: how Linux 7.3 (+ audio-speakers 0014) can set it up:
#   'named'   audioreach.c has a module-type case in audioreach_set_media_format()
#   'generic' only the generic topology blob path (module priv data, type 0x01001006), which
#             7.3 sends only for SMECNS_V2 (default: case does nothing): needs a kernel change
#   'none'    nothing to send (module works with its power-on defaults and the graph links)
# name_grade: V = Linux source / public topology, I = inferred (see the evidence file)
MODULES = {
    0x07001000: ("WR_SHARED_MEM_EP", "P", "named", "V"),
    0x07001001: ("RD_SHARED_MEM_EP", "P", "none", "V"),
    0x07001002: ("GAIN", "P", "named", "V"),
    0x07001003: ("PCM_CNV", "P", "named", "V"),
    0x07001004: ("PCM_ENC", "P", "named", "V"),
    0x07001005: ("PCM_DEC", "P", "named", "V"),
    0x07001006: ("SH_MEM_PULL_MODE", "P", "named", "V"),
    0x07001007: ("SH_MEM_PUSH_MODE", "P", "none", "V"),
    0x07001008: ("PLACEHOLDER_ENCODER", "P", "named", "V"),
    0x07001009: ("PLACEHOLDER_DECODER", "P", "named", "V"),
    0x0700100A: ("I2S_SINK", "P", "named", "V"),
    0x0700100B: ("I2S_SOURCE", "P", "named", "V"),
    0x07001010: ("SAL", "P", "named", "V"),
    0x07001015: ("MFC", "P", "named", "V"),
    0x0700101A: ("DATA_LOGGING", "M", "named", "V"),
    0x0700101B: ("VOL_CTRL", "P", "none", "V"),
    0x07001023: ("CODEC_DMA_SINK", "P", "named", "V"),
    0x07001024: ("CODEC_DMA_SOURCE", "P", "named", "V"),
    0x07001031: ("SMECNS_V2", "Q", "named", "V"),
    0x0700104D: ("GAPLESS", "P", "named", "V"),
    0x07001069: ("DISPLAY_PORT_SINK", "P", "named", "V"),
    0x070010E2: ("SPEAKER_PROTECTION", "S", "named", "V"),
    0x070010E3: ("SPEAKER_PROTECTION_VI", "S", "named", "V"),
    0x070010E4: ("CPS_DATA_ROUTER", "S", "generic", "I"),
}
# Names resolved by the evidence file (REA on qcadsp8380.mbn, see names.json next to this file)
NAMES_FILE = HERE / "module-names.json"


def load_extra_names():
    if not NAMES_FILE.exists():
        return
    for key, row in json.loads(NAMES_FILE.read_text()).items():
        if key.startswith("_"):
            continue
        MODULES.setdefault(int(key, 16), tuple(row))


def adsp_module_table(path):
    """Module ids registered in the ADSP image (AMDB static table: flags, id, 2 code pointers).

    Verified layout: runs of 16-byte entries {u32 flags, u32 module_id, u32 ptr, u32 ptr} with
    module_id in 0x07000000..0x0701ffff. Returns {module_id: (file_offset, flags)}.
    """
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != ADSP_SHA256:
        raise ValueError("ADSP image SHA-256 does not match the catalogued input")
    found, off, n = {}, 0, len(data) - 16
    words = struct.unpack_from(f"<{len(data) // 4}I", data, 0)
    for i in range(0, len(words) - 4):
        flags, mid, p1, p2 = words[i:i + 4]
        if 0 < flags <= 0x20 and 0x07001000 <= mid <= 0x0701ffff and (p1 >> 28) in (0, 0xb, 0x6) \
                and (p2 >> 28) in (0, 0xb, 0x6) and (p1 == 0) == (p2 == 0):
            nxt = words[i + 4:i + 6]
            prv = words[i - 3:i - 2] if i >= 3 else [0]
            if (0x07000000 <= nxt[1] <= 0x0701ffff) or (0x07000000 <= prv[0] <= 0x0701ffff):
                found[mid] = (i * 4, flags)
    return found


def adsp_dynamic_table(path):
    """Dynamically loaded modules: {module_id: (so_name, capi_name)} from the AMDB dynamic table.

    Verified layout in qcadsp8380.mbn: entries {u32 flags(4|0xa), u32 module_id, u32 1, u32 ptr_so,
    u32 ptr_capi}; the pointers address NUL-terminated names in the image's read-only data. Each
    .so is shipped in the Windows ADSP folder (ADSP/*.so.1) and listed in /statichashes/.
    """
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != ADSP_SHA256:
        raise ValueError("ADSP image SHA-256 does not match the catalogued input")
    # pointer->file offset delta is fixed by one known pair: the table entry of SMECNS_V2 (0x07001031)
    words = struct.unpack_from(f"<{len(data) // 4}I", data, 0)
    delta = None
    for i in range(len(words) - 5):
        fl, mid, one, p1, p2 = words[i:i + 5]
        if mid == 0x07001031 and one == 1 and fl in (4, 0xA):
            delta = p1 - (data.find(b"\0smecns_v2_module_fvxiii.so.1\0") + 1)
            break
    if delta is None:
        return {}

    def cstr(va):
        off = va - delta
        end = data.find(b"\0", off, off + 96)
        s = data[off:end]
        return s.decode("latin1") if end > 0 and s and all(32 <= c < 127 for c in s) else None

    out = {}
    for i in range(len(words) - 5):
        fl, mid, one, p1, p2 = words[i:i + 5]
        if fl in (4, 0xA) and one == 1 and 0x07001000 <= mid <= 0x0701FFFF and (p1 >> 20) == (p2 >> 20):
            a, b = cstr(p1), cstr(p2)
            if a and b and a.endswith((".so.1", ".so")) and b.startswith("capi_"):
                out.setdefault(mid, (a, b))
    return out


def all_graphs(acdb):
    out = []
    for offset, keys, (_, ref) in acdb.lookup("GKVL", 2):
        base, data = acdb.pool[ref]
        c, sgs = ai.Cursor(data, base), []
        for _ in range(c.u32()):
            sg, size = c.words(2)
            start = c.base + c.pos
            q = ai.Cursor(c.take(size), start)
            q.take(q.u32())
            psz = q.u32()
            pbase = q.base + q.pos
            sgs.append((sg, ai.graph_parameters(q.take(psz), pbase)))
            q.done()
        c.done()
        out.append((keys, sgs))
    return out


def all_calibration(acdb):
    """{instance: {param: {'sizes': set, 'rows': n}}} over every CDLU row (sizes only)."""
    de_base, de = acdb.chunks["CDDE"]
    do_base, do = acdb.chunks["CDDO"]
    res = collections.defaultdict(lambda: collections.defaultdict(lambda: {"sizes": set(), "rows": 0}))
    for _, keys, (de_ref, do_ref, _) in acdb.lookup("CDLU", 3):
        a, b = ai.Cursor(de[de_ref:], de_base + de_ref), ai.Cursor(do[do_ref:], do_base + do_ref)
        count = a.u32()
        if b.u32() != count:
            raise ValueError("calibration count mismatch")
        for _ in range(count):
            iid, pid = a.words(2)
            _, payload = acdb.pool[b.u32()]
            slot = res[iid][pid]
            slot["sizes"].add(len(payload))
            slot["rows"] += 1
    return res


def order_chain(modules, conns):
    """Topological order of one subgraph's modules by its data connections."""
    succ = collections.defaultdict(list)
    indeg = {m: 0 for m in modules}
    for c in conns:
        s, d = int(c["source"], 16), int(c["destination"], 16)
        if s in indeg and d in indeg:
            succ[s].append(d)
            indeg[d] += 1
    ready = sorted(m for m, n in indeg.items() if n == 0)
    order = []
    while ready:
        m = ready.pop(0)
        order.append(m)
        for d in sorted(succ[m]):
            indeg[d] -= 1
            if indeg[d] == 0:
                ready.append(d)
    return order + [m for m in modules if m not in order]


# Quality role of the dynamically loaded modules (names Verified from the image, functions Inference)
DYN_CLASS = {"capi_smecns_v2": "Q", "capi_ffecns": "Q", "capi_fluence_ef": "Q", "capi_fluence_nn": "Q",
             "capi_fluence_nn_ns": "Q", "capi_fluence_bs": "Q", "capi_fluence_pro_vc": "Q",
             "capi_fluence_pro_vr": "Q", "capi_sm_fluence_sb": "Q", "capi_mm_fluence_sb": "Q",
             "capi_ans": "Q", "capi_audiosphere": "Q", "capi_sdd": "Q?", "capi_hdr": "Q?", "capi_cfcm": "Q?"}


def describe(acdb, adsp=None, dyn=None):
    load_extra_names()
    dyn = dyn or {}
    cal = all_calibration(acdb)
    graphs = []
    for keys, sgs in all_graphs(acdb):
        g = {"keys": [ai.hx(k) if k > 255 else k for k in keys], "subgraphs": []}
        for sg, params in sgs:
            mods, conns, props, conts = {}, [], {}, []
            for p in params:
                for m in p.get("modules", []):
                    mods[int(m["instance"], 16)] = int(m["module"], 16)
                conns += p.get("connections", [])
                if p["parameter"] == "0x08001001":
                    for o in p["objects"]:
                        props = {x["id"]: x["words"] for x in o["properties"]}
                if p["parameter"] == "0x08001000":
                    for o in p["objects"]:
                        pr = {x["id"]: x["words"] for x in o["properties"]}
                        conts.append({"container": o["instance"], "capability": pr.get("0x08001011"),
                                      "proc_domain": pr.get("0x08001014"), "graph_pos": pr.get("0x08001012"),
                                      "stack": pr.get("0x08001013")})
            chain = []
            for iid in order_chain(list(mods), conns):
                mid = mods[iid]
                name, cls, handler, grade = MODULES.get(mid, (None, "?", "generic", None))
                registration = "static" if adsp is not None and mid in adsp else None
                if mid in dyn:
                    so, capi = dyn[mid]
                    name, cls, grade = capi, DYN_CLASS.get(capi, "P?"), "V"
                    handler = "named" if mid == 0x07001031 else "generic"
                    registration = f"dynamic:{so}"
                sizes = [max(v["sizes"]) for v in cal.get(iid, {}).values()]
                if cls == "?":
                    # Unnamed module: only structure can speak. A module with tuning payloads of
                    # 100 bytes or more is a quality CANDIDATE (Hypothesis); without payloads it is
                    # treated as plumbing (Hypothesis).
                    cls = "Q?" if sizes and max(sizes) >= 100 else "P?"
                chain.append({
                    "instance": ai.hx(iid), "module": ai.hx(mid), "name": name or "UNNAMED",
                    "class": cls, "linux_handler": handler, "name_grade": grade,
                    "in_adsp": None if adsp is None else registration is not None,
                    "registration": registration,
                    "cal_params": [{"param": ai.hx(pid), "sizes": sorted(v["sizes"]), "rows": v["rows"]}
                                   for pid, v in sorted(cal.get(iid, {}).items())],
                })
            g["subgraphs"].append({
                "subgraph": ai.hx(sg), "perf_mode": props.get("0x0800100e"),
                "direction": props.get("0x0800100f"), "scenario": props.get("0x08001010"),
                "containers": conts, "chain": chain,
                "connections": len(conns)})
        graphs.append(g)
    return {"schema": "sp11-acdb-usecases-v1", "acdb_sha256": ai.EXPECTED_SHA256, "graphs": graphs}


def summary(doc):
    ids = collections.OrderedDict()
    for g in doc["graphs"]:
        for sg in g["subgraphs"]:
            for m in sg["chain"]:
                row = ids.setdefault(m["module"], {"name": m["name"], "class": m["class"], "n": 0,
                                                   "adsp": m["in_adsp"], "cal": set()})
                row["n"] += 1
                row["cal"].update(p["param"] for p in m["cal_params"])
    print(f"{len(doc['graphs'])} graph key vectors, "
          f"{sum(len(g['subgraphs']) for g in doc['graphs'])} subgraph instances")
    for mid, r in sorted(ids.items()):
        print(f"{mid} {r['name']:<22} class {r['class']} used {r['n']:>3} adsp {r['adsp']} "
              f"calparams {len(r['cal'])}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("acdb", type=Path)
    ap.add_argument("--adsp", type=Path, help="qcadsp8380.mbn (checks every module id is registered)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    acdb = ai.Acdb(a.acdb.read_bytes())
    adsp = adsp_module_table(a.adsp) if a.adsp else None
    dyn = adsp_dynamic_table(a.adsp) if a.adsp else None
    doc = describe(acdb, adsp, dyn)
    if adsp is not None:
        doc["adsp_sha256"] = ADSP_SHA256
        doc["adsp_registered_modules"] = len(adsp)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(doc, indent=1) + "\n")
        a.out.chmod(0o600)
    if a.summary or not a.out:
        summary(doc)


if __name__ == "__main__":
    main()
