#!/usr/bin/env python3
"""Generate the Windows-tuned capture/playback quality data for the Surface Pro 11 (PRIVATE ONLY).

Inputs (read only): the pinned REV_0D ACDB and the ADSP image (module registration check).
Outputs go to a private directory, normally out/firmware-private/audio/ (S5, D25). Nothing
written here is public and nothing is committed. Offline verification only.

  sp11q-plan.json                 per use case: graph description (subgraph, containers, modules with
                                  instance ids, connections) and the replay decision per module
  <card>-sp11q.bin                calibration records of the CAPTURE use cases (ungated)
  <card>-sp11q-dyn.bin            records of modules loaded dynamically from the Windows ADSP *.so files
                                  (smecns_v2, ffecns, fluence_*): only for a topology variant that is
                                  used after the .so files are served to the ADSP (never by default)
  <card>-sp11q-spk.bin            calibration records of the SPEAKER stream use cases (GATED, only
                                  with --include-playback; see "merge interface" below)

Replay rule per module (a record is written only when all hold):
  1. the module id is registered in the ADSP image, in the static table or in the dynamic table
     (an unregistered module cannot be instantiated: plan only; dynamic ones go to the -dyn file);
  2. the (instance, parameter) pair has exactly one payload in the ACDB or all payloads are identical
     (otherwise the key semantics that select the row are unknown: plan only, listed as ambiguous);
  3. the payload is at most 4 KiB (the limit audio-speakers patch 0014 enforces for one record);
  4. the instance is not owned by the speaker protection guard (see GUARD_*).

Merge interface with the closed-loop speaker protection (audio-speakers owner):
  - The guard owns: module instances SP/VI/CPS and their feeders (GUARD_INSTANCES), the module ids
    0x070010e2/e3/e4 and the SAL limiter enable (parameter 0x0800101e must stay 1). This tool never
    writes a record for them, and refuses to run if an input would.
  - sp11q-spk.bin is a separate, GATED file: the kernel must apply it only after the guard reports the
    closed-loop graph up and fault free (the same condition that lifts the 0009 refusal). Without the
    guard the file is never read. The records only target stream-side modules; the order in the graph
    keeps SPEAKER_PROTECTION downstream of every tuned module, so tuning can change the signal the
    guard sees but never bypasses it (Verified from the ACDB chain: SP is after SAL and the stream).
  - The sp11cl file keeps sole authority over the guard records; if a record of sp11q and of sp11cl
    target the same (instance, parameter) the loader must keep sp11cl (the generator guarantees
    there is none; --check-against-sp11cl verifies it against a given sp11cl file).

File format SP11Q001 (little endian):
  header  : "SP11Q001", u32 flags (bit0 GATED), u32 n_sets, u32 payload_len, u32 crc32_le(payload)
  set     : u32 anchor_instance, u32 acdb_subgraph, u32 n_records, then records
  record  : u32 instance, u32 param_id, u32 size, data[size] padded to 4
"""

import argparse
import collections
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import acdb_usecases as uc  # noqa: E402
import acdb_inspect as ai  # noqa: E402

CARD = "X1E80100-Microsoft-Surface-Pro-11"
DRIVER = "x1e80100"
FLAG_GATED = 1
FLAG_DYNAMIC = 2
MAX_RECORD = 4096
GUARD_INSTANCES = {0x4027, 0x4024, 0x4028, 0x4026, 0x4025, 0x402B, 0x402A, 0x4029}
GUARD_MODULES = {0x070010E2, 0x070010E3, 0x070010E4}
SAL_LIMITER_ENABLE = 0x0800101E
SAL = 0x07001010
STREAM_EPS = {0x07001000, 0x07001006}   # WR_SHARED_MEM_EP, SH_MEM_PULL_MODE (playback)
CAPTURE_EPS = {0x07001007, 0x07001001}  # SH_MEM_PUSH_MODE, RD_SHARED_MEM_EP (capture)
CODEC_SRC, CODEC_SNK = 0x07001024, 0x07001023


def crc32_le(data):
    return zlib.crc32(data) ^ 0xFFFFFFFF


def payload_rows(acdb, wanted):
    """{(instance, param): [payload, ...]} for the wanted instances, over every CDLU row."""
    de_base, de = acdb.chunks["CDDE"]
    do_base, do = acdb.chunks["CDDO"]
    out = collections.defaultdict(list)
    for _, keys, (de_ref, do_ref, _) in acdb.lookup("CDLU", 3):
        a, b = ai.Cursor(de[de_ref:], de_base + de_ref), ai.Cursor(do[do_ref:], do_base + do_ref)
        count = a.u32()
        b.u32()
        for _ in range(count):
            iid, pid = a.words(2)
            _, payload = acdb.pool[b.u32()]
            if iid in wanted:
                out[(iid, pid)].append(bytes(payload))
    return out


def classify_subgraph(sg):
    mods = {int(m["module"], 16) for m in sg["chain"]}
    if mods & GUARD_MODULES:
        return "speaker-device-guarded"
    if sg["direction"] == [2] and mods & STREAM_EPS:
        return "playback-stream"
    if sg["direction"] == [1] and mods & CAPTURE_EPS:
        return "capture-stream"
    if sg["direction"] == [2] and CODEC_SNK in mods:
        return "playback-device"
    if sg["direction"] == [1] and CODEC_SRC in mods:
        return "capture-device"
    if sg["direction"] == [1]:
        return "capture-processing"
    if sg["direction"] == [2]:
        return "playback-processing"
    return "other"


def usecase_of(keys):
    """Use-case label from the graph key vector. Inference: in the 6-key vectors the last key selects
    the device/use case (1 speaker RX, 3 other RX, 2/4/5/16 microphone TX, 9 uplink processing,
    12/13 voice call, 8/10/11/15 RX processing only); 5-key vectors are microphone variants. The key
    ids are not named in the ACDB; the meaning rests on the module chains (see the evidence file)."""
    if len(keys) == 6:
        return {1: "speaker", 3: "rx-other", 2: "mic", 4: "mic", 5: "mic", 16: "mic", 9: "uplink",
                12: "voice", 13: "voice", 8: "rx-proc", 10: "rx-proc", 11: "rx-proc",
                15: "rx-proc", 14: "other"}.get(keys[-1], "other")
    return "mic" if len(keys) == 5 else "other"


def replay_decisions(acdb, doc):
    """Per subgraph: which (instance, param) pairs can be replayed, which are plan-only and why."""
    wanted = {int(m["instance"], 16) for g in doc["graphs"] for sg in g["subgraphs"] for m in sg["chain"]}
    rows = payload_rows(acdb, wanted)
    plan = []
    for gi, g in enumerate(doc["graphs"]):
        for sg in g["subgraphs"]:
            kind = classify_subgraph(sg)
            decisions, records = [], []
            for m in sg["chain"]:
                iid, mid = int(m["instance"], 16), int(m["module"], 16)
                for cp in m["cal_params"]:
                    pid = int(cp["param"], 16)
                    pays = rows.get((iid, pid), [])
                    why = None
                    if iid in GUARD_INSTANCES or mid in GUARD_MODULES:
                        why = "guard-owned"
                    elif pid == SAL_LIMITER_ENABLE:
                        why = "guard-owned (SAL limiter)"
                    elif m["in_adsp"] is False:
                        why = "not registered in the ADSP image (static or dynamic table)"
                    elif not pays:
                        why = "no payload"
                    elif len(set(pays)) != 1:
                        why = f"ambiguous ({len(pays)} rows differ; key semantics unknown)"
                    elif len(pays[0]) > MAX_RECORD:
                        why = f"payload {len(pays[0])} B > {MAX_RECORD} B (needs chunked or out-of-band set)"
                    elif m["class"] in ("P", "M") and m["linux_handler"] == "named":
                        why = "framework-managed (the kernel sets it from the topology)"
                    elif m["class"] == "P?" and pid != 0x08001026:
                        why = "plumbing candidate (format/routing comes from the topology)"
                    dyn = (m.get("registration") or "").startswith("dynamic:")
                    decisions.append({"dynamic": dyn, "instance": m["instance"], "module": m["module"], "name": m["name"],
                                      "class": m["class"], "param": cp["param"],
                                      "size": max(cp["sizes"]), "replay": why is None, "reason": why})
                    if why is None:
                        records.append((iid, pid, pays[0], dyn))
            plan.append({"graph_keys": g["keys"], "subgraph": sg["subgraph"], "kind": kind,
                         "usecase": usecase_of(g["keys"]),
                         "perf_mode": sg["perf_mode"], "decisions": decisions, "records": records,
                         "anchor": int(sg["chain"][0]["instance"], 16) if sg["chain"] else None})
    return plan


def build_sets(plan, kinds, usecases, dynamic=False):
    """Group the records of the selected kinds into sets, deduplicating identical sets."""
    seen, sets = set(), []
    for p in plan:
        recs = [r for r in p["records"] if r[3] == dynamic]
        if p["kind"] not in kinds or p["usecase"] not in usecases or not recs or p["anchor"] is None:
            continue
        p = dict(p, records=recs)
        key = (p["anchor"], tuple((i, pid, hashlib.sha256(d).digest()) for i, pid, d, _ in recs))
        if key in seen:
            continue
        seen.add(key)
        sets.append(p)
    return sets


def pack(sets, flags):
    body = b""
    for p in sets:
        body += struct.pack("<3I", p["anchor"], int(p["subgraph"], 16), len(p["records"]))
        for iid, pid, data, _ in p["records"]:
            if iid in GUARD_INSTANCES:
                raise ValueError("refusing to write a guard-owned instance")
            body += struct.pack("<3I", iid, pid, len(data)) + data + b"\0" * (-len(data) % 4)
    return b"SP11Q001" + struct.pack("<4I", flags, len(sets), len(body), crc32_le(body)) + body


def decode(blob):
    """Independent re-parse used by --self-test."""
    assert blob[:8] == b"SP11Q001"
    flags, n_sets, plen, crc = struct.unpack_from("<4I", blob, 8)
    body = blob[24:]
    assert plen == len(body) and crc == crc32_le(body)
    off, sets = 0, []
    for _ in range(n_sets):
        anchor, sg, n = struct.unpack_from("<3I", body, off)
        off += 12
        recs = []
        for _ in range(n):
            iid, pid, size = struct.unpack_from("<3I", body, off)
            recs.append((iid, pid, body[off + 12:off + 12 + size]))
            off += 12 + size + (-size % 4)
        sets.append((anchor, sg, recs))
    assert off == plen
    return flags, sets


def graph_spec(doc, plan, kinds):
    """The structural description the topology m4 generator consumes (ids, no calibration)."""
    out = []
    for g in doc["graphs"]:
        for sg in g["subgraphs"]:
            kind = next(p["kind"] for p in plan if p["subgraph"] == sg["subgraph"] and p["graph_keys"] == g["keys"])
            if kind in kinds:
                out.append({"graph_keys": g["keys"], "subgraph": sg["subgraph"], "kind": kind,
                            "perf_mode": sg["perf_mode"], "containers": sg["containers"],
                            "modules": [{k: m[k] for k in ("instance", "module", "name", "class", "in_adsp")}
                                        for m in sg["chain"]]})
    return out


def write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--acdb", type=Path, required=True)
    ap.add_argument("--adsp", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True, help="private, e.g. out/firmware-private/audio")
    ap.add_argument("--include-playback", action="store_true",
                    help="also write the GATED speaker stream records (never loaded without the guard)")
    ap.add_argument("--check-against-sp11cl", type=Path, help="existing sp11cl file: refuse any overlap")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    acdb = ai.Acdb(a.acdb.read_bytes())
    doc = uc.describe(acdb, uc.adsp_module_table(a.adsp), uc.adsp_dynamic_table(a.adsp))
    plan = replay_decisions(acdb, doc)
    base = a.out_dir / "qcom" / DRIVER
    out = {}

    cap_kinds = {"capture-stream", "capture-device", "capture-processing"}
    spk_kinds = {"playback-stream", "playback-processing"}
    cap_uc, spk_uc = {"mic", "uplink", "voice"}, {"speaker"}
    cap = build_sets(plan, cap_kinds, cap_uc)
    out["sp11q"] = pack(cap, 0)
    out["sp11q-dyn"] = pack(build_sets(plan, cap_kinds, cap_uc, dynamic=True), FLAG_DYNAMIC)
    if a.include_playback:
        out["sp11q-spk"] = pack(build_sets(plan, spk_kinds, spk_uc), FLAG_GATED)

    if a.check_against_sp11cl:
        cl = a.check_against_sp11cl.read_bytes()
        n_links, n_cal = struct.unpack_from("<2I", cl, 8)
        off, taken = 36 + 20 * n_links, set()
        for _ in range(n_cal):
            iid, pid, size = struct.unpack_from("<3I", cl, off)
            taken.add((iid, pid))
            off += 12 + size + (-size % 4)
        for blob in out.values():
            for _, _, recs in decode(blob)[1]:
                clash = [(i, p) for i, p, _ in recs if (i, p) in taken]
                if clash:
                    raise SystemExit(f"overlap with sp11cl: {clash}")

    for name, blob in out.items():
        write_private(base / f"{CARD}-{name}.bin", blob)
    summary = {"plan_subgraphs": len(plan),
               "by_kind": dict(collections.Counter(p["kind"] for p in plan)),
               "by_usecase": dict(collections.Counter(p["usecase"] for p in plan)),
               "records_replayable": sum(len(p["records"]) for p in plan),
               "decisions_plan_only": dict(collections.Counter(
                   (d["reason"] or "").split(" (")[0] for p in plan for d in p["decisions"] if not d["replay"]))}
    # The plan carries ids, sizes and reasons only, never payloads
    spec = {"schema": "sp11q-plan-v1", "acdb_sha256": doc["acdb_sha256"], "summary": summary,
            "capture": graph_spec(doc, plan, cap_kinds), "playback": graph_spec(doc, plan, spk_kinds),
            "decisions": [{k: v for k, v in p.items() if k != "records"} for p in plan]}
    write_private(a.out_dir / "sp11q-plan.json", (json.dumps(spec, indent=1) + "\n").encode())

    if a.self_test:
        for name, blob in out.items():
            flags, sets = decode(blob)
            assert all(i not in GUARD_INSTANCES for _, _, recs in sets for i, _, _ in recs)
            assert (flags & FLAG_GATED) == (1 if name.endswith("spk") else 0)
            assert (flags & FLAG_DYNAMIC) == (2 if name.endswith("dyn") else 0)
            print(f"self-test ok: {name}: {len(sets)} sets, {sum(len(r) for _, _, r in sets)} records")
    print(json.dumps(summary, indent=1))
    print(json.dumps({n: hashlib.sha256(b).hexdigest() for n, b in out.items()}, indent=1))


if __name__ == "__main__":
    main()
