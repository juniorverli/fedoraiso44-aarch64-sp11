#!/usr/bin/env python3
"""Generate the closed-loop speaker protection files for the Surface Pro 11.

Inputs (read only): the pinned REV_0D ACDB (Windows data, never in git) and,
for the topology step, the m4 overlay in m4/ on top of the public audioreach-topology.
Outputs go to a private directory, normally out/firmware-private/audio/, and are
installed only by the private image mode (D25, S5). Nothing here is public.

  sp11cl   <card>-sp11cl.bin    control links + calibration records of the model
  sp11cal  <card>-sp11cal.bin   R0/T0 of this unit (measured, or nominal on request)
  tplg     <card>-tplg.bin      the public topology plus the speaker protection chains; built by
                                build-closedloop-topology.sh from m4/ (this script only writes the
                                instance ids it needs, see --emit-ids)

File formats are defined by sound/soc/qcom/qdsp6/audioreach-sp11.c
(audio-speakers patch 0014). Offline verification only: nothing here has been
loaded by a kernel yet.
"""

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import acdb_inspect  # noqa: E402

SUBGRAPH = "0xb0000001"
SP, VI, CPS = 0x4027, 0x4024, 0x4028
CAL_INSTANCES = {SP, VI, CPS}
RE_PARAM = 0x08001535
FLAG_CPS = 1
FLAG_NOMINAL = 1
T0_NOMINAL_Q6 = 25 * 64
CARD = "X1E80100-Microsoft-Surface-Pro-11"
DRIVER = "x1e80100"


def crc32_le(data):
    """The kernel's crc32_le(~0, data): zlib's CRC without the final inversion."""
    return zlib.crc32(data) ^ 0xFFFFFFFF


def find_graph(acdb):
    """The subgraph with the closed-loop modules, its links and its nominal Re."""
    for cand in acdb.graphs():
        for sg in cand["subgraphs"]:
            if sg["subgraph"] != SUBGRAPH:
                continue
            links, modules = [], set()
            for par in sg["parameters"]:
                for m in par.get("modules", []):
                    modules.add(int(m["instance"], 16))
                links += par.get("control_links", [])
            if {SP, VI, CPS} <= modules and links:
                return modules, links
    raise ValueError("no closed-loop speaker subgraph found in the ACDB")


MID_SP, MID_VI, MID_CPS = 0x070010E2, 0x070010E3, 0x070010E4
MID_LOGGER, MID_DMA_SRC = 0x0700101A, 0x07001024


def find_roles(acdb):
    """Instance ids of the topology roles, found by module id and by the graph's own connections.

    Returns {role: instance id}. The checks tie every id to the Windows graph: the sense chain
    must be CODEC_DMA_SOURCE -> DATA_LOGGING -> SPEAKER_PROTECTION_VI, and SP_VI must have no
    consumer. The CPS chain is optional and only reported when it has the expected shape.
    """
    for cand in acdb.graphs():
        for sg in cand["subgraphs"]:
            if sg["subgraph"] != SUBGRAPH:
                continue
            mods, conns = {}, []
            for par in sg["parameters"]:
                for m in par.get("modules", []):
                    mods[int(m["instance"], 16)] = int(m["module"], 16)
                conns += par.get("connections", [])
            by_mid = {}
            for iid, mid in mods.items():
                by_mid.setdefault(mid, []).append(iid)
            pred = {int(c["destination"], 16): int(c["source"], 16) for c in conns}
            succ = {int(c["source"], 16) for c in conns}
            roles = {}
            for role, mid in (("sp", MID_SP), ("vi", MID_VI), ("cps", MID_CPS)):
                if len(by_mid.get(mid, [])) != 1:
                    raise ValueError(f"expected one module 0x{mid:08x}, found {by_mid.get(mid)}")
                roles[role] = by_mid[mid][0]
            if roles["vi"] in succ:
                raise ValueError("SP_VI has a consumer: the sense chain is not a dead end")
            log = pred.get(roles["vi"])
            dma = pred.get(log)
            if mods.get(log) != MID_LOGGER or mods.get(dma) != MID_DMA_SRC:
                raise ValueError("the sense chain is not CODEC_DMA_SOURCE -> DATA_LOGGING -> VI")
            roles["vi_log"], roles["vi_dma"] = log, dma
            return roles
    raise ValueError("no closed-loop speaker subgraph found in the ACDB")


def write_ids_m4(roles, path):
    """The private m4 include of the topology generator (module instance ids of the Windows graph)."""
    names = {"sp": "SP11_SP_IID", "vi": "SP11_VI_IID", "vi_log": "SP11_VILOG_IID",
             "vi_dma": "SP11_VIDMA_IID"}
    lines = ["dnl Generated from the Windows ACDB: private, never commit."]
    lines += [f"define(`{names[k]}', `0x{roles[k]:08x}') dnl" for k in names]
    write_private(path, ("\n".join(lines) + "\n").encode())


def build_links(modules, links, with_cps):
    """Links whose two peers are in the subgraph. The CPS link only on request."""
    result = []
    for link in links:
        p1, p2 = int(link["peer1"], 16), int(link["peer2"], 16)
        if p1 not in modules or p2 not in modules:
            continue  # peer outside this subgraph (the WSA endpoint link)
        if p2 != SP:
            raise ValueError("expected the speaker protection module as peer 2")
        if p1 == CPS and not with_cps:
            continue
        intent = next(prop["words"][1] for prop in link["properties"]
                      if prop["id"] == "0x08001062")
        result.append((p1, int(link["port1"], 16), p2, int(link["port2"], 16), intent))
    if not any(link[0] == VI for link in result):
        raise ValueError("the V/I control link is missing")
    return result


def nominal_re_q24(records):
    for iid, pid, payload in records:
        if iid == VI and pid == RE_PARAM:
            words = struct.unpack("<27I", payload)
            return [words[1], words[9]]
    raise ValueError("nominal Re not found")


def build_sp11cl(links, records, flags, nominal_re):
    payload = b"".join(struct.pack("<5I", *link) for link in links)
    for iid, pid, data in records:
        payload += struct.pack("<3I", iid, pid, len(data)) + data + b"\0" * (-len(data) % 4)
    header = (b"SP11CL01" + struct.pack("<3I", len(links), len(records), flags)
              + struct.pack("<2I", *nominal_re)
              + struct.pack("<2I", len(payload), crc32_le(payload)))
    return header + payload


def build_sp11cal(r0_q24, t0_q6, nominal):
    body = b"SP11CA01" + struct.pack("<2I", FLAG_NOMINAL if nominal else 0, 2)
    for r0, t0 in zip(r0_q24, t0_q6):
        body += struct.pack("<IhH", r0, t0, 0)
    return body + struct.pack("<I", crc32_le(body))


def decode_sp11cl(blob):
    """Independent re-parse of what build_sp11cl wrote; used by --self-test."""
    assert blob[:8] == b"SP11CL01"
    n_links, n_cal, flags, re0, re1, plen, crc = struct.unpack_from("<7I", blob, 8)
    payload = blob[36:]
    assert plen == len(payload) and crc == crc32_le(payload)
    off, links = 0, []
    for _ in range(n_links):
        links.append(struct.unpack_from("<5I", payload, off))
        off += 20
    recs = []
    for _ in range(n_cal):
        iid, pid, size = struct.unpack_from("<3I", payload, off)
        recs.append((iid, pid, payload[off + 12:off + 12 + size]))
        off += 12 + size + (-size % 4)
    assert off == plen
    return n_links, flags, (re0, re1), links, recs


def write_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--acdb", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True,
                    help="private output directory, for example out/firmware-private/audio")
    ap.add_argument("--with-cps", action="store_true",
                    help="require the CPS feedback (control link and stream)")
    cal = ap.add_mutually_exclusive_group()
    cal.add_argument("--nominal-cal", action="store_true",
                     help="write a NOMINAL unit calibration: Re from the ACDB, T0 25 C")
    cal.add_argument("--measured", nargs=4, type=float,
                     metavar=("R0_LEFT", "R0_RIGHT", "T0_LEFT", "T0_RIGHT"),
                     help="write a measured unit calibration (ohm, degC)")
    ap.add_argument("--emit-ids", type=Path, metavar="FILE",
                    help="write the private m4 include with the instance ids for the topology and exit")
    ap.add_argument("--self-test", action="store_true", help="decode what was written")
    args = ap.parse_args()

    acdb = acdb_inspect.Acdb(args.acdb.read_bytes())
    if args.emit_ids:
        roles = find_roles(acdb)
        write_ids_m4(roles, args.emit_ids)
        print(json.dumps({k: f"0x{v:08x}" for k, v in roles.items()}))
        return
    modules, links = find_graph(acdb)
    records = acdb.calibration_payloads(CAL_INSTANCES)
    if not records:
        raise SystemExit("no calibration records")
    links = build_links(modules, links, args.with_cps)
    nominal = nominal_re_q24(records)

    base = args.out_dir / "qcom" / DRIVER
    out = {}
    out["sp11cl"] = build_sp11cl(links, records, FLAG_CPS if args.with_cps else 0, nominal)
    write_private(base / f"{CARD}-sp11cl.bin", out["sp11cl"])
    if args.nominal_cal:
        out["sp11cal"] = build_sp11cal(nominal, [T0_NOMINAL_Q6] * 2, True)
    elif args.measured:
        r0l, r0r, t0l, t0r = args.measured
        out["sp11cal"] = build_sp11cal([round(r0l * 2**24), round(r0r * 2**24)],
                                       [round(t0l * 64), round(t0r * 64)], False)
    if "sp11cal" in out:
        write_private(base / f"{CARD}-sp11cal.bin", out["sp11cal"])

    if args.self_test:
        n_links, flags, re, dec_links, recs = decode_sp11cl(out["sp11cl"])
        assert dec_links == links and len(recs) == len(records)
        assert [bytes(r[2]) for r in recs] == [r[2] for r in records]
        print(f"self-test ok: {n_links} links, {len(recs)} records, flags {flags}, "
              f"Re {[x / 2**24 for x in re]}")

    # Hashes only: the files are Windows-derived and private (S5)
    print(json.dumps({name: hashlib.sha256(blob).hexdigest() for name, blob in out.items()},
                     indent=1))


if __name__ == "__main__":
    main()
