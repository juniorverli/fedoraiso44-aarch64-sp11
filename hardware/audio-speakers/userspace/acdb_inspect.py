#!/usr/bin/env python3
"""Inspect the pinned Denali ACDB as DATA; never disassemble or enable audio.

JSON contains graph facts and parameter references, not calibration payloads.
Generated artifacts belong in private out/, never in git. This is an ACDB v4
container decoder, not a general ACDB implementation or a runnable topology.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SHA256 = "a0a8635ba65127180a1caef46af61c00171c9a93cbf8b5f5650709b4638decde"
# Module ids as Linux 7.3 names them (sound/soc/qcom/qdsp6/audioreach.h). An earlier version of this
# table labelled 0x0700101a "MFC" and 0x07001013 "DATA_LOGGING"; Linux says 0x07001015 is the MFC and
# 0x0700101a the DATA_LOGGING module. 0x07001011 and 0x07001013 have no Linux name: they are labelled
# by id only (the old guess "SPLITTER" for 0x07001011 is unverified).
MODULE_NAMES = {
    0x07001010: "SAL", 0x07001015: "MFC", 0x0700101A: "DATA_LOGGING",
    0x07001023: "CODEC_DMA_SINK", 0x07001024: "CODEC_DMA_SOURCE",
    0x070010E2: "SPEAKER_PROTECTION", 0x070010E3: "SPEAKER_PROTECTION_VI",
    0x070010E4: "CPS_DATA_ROUTER",
}


def hx(value):
    return f"0x{value:08x}"


class Cursor:
    def __init__(self, data, base=0):
        self.data, self.base, self.pos = data, base, 0

    def take(self, size):
        if size < 0 or size > len(self.data) - self.pos:
            raise ValueError(f"truncated record at {self.base + self.pos:#x}")
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def words(self, count):
        return [self.u32() for _ in range(count)]

    def done(self):
        if self.pos != len(self.data):
            raise ValueError(f"unconsumed record at {self.base + self.pos:#x}")


def properties(c, count):
    result = []
    for _ in range(count):
        pid, size = c.words(2)
        data = c.take(size)
        if size % 4:
            raise ValueError("non-word graph property")
        result.append({"id": hx(pid), "words": Cursor(data).words(size // 4)})
    return result


def module_list(data):
    c, result = Cursor(data), []
    for _ in range(c.u32()):
        sg, container, count = c.words(3)
        for _ in range(count):
            mid, iid = c.words(2)
            result.append(dict(subgraph=hx(sg), container=hx(container),
                               module=hx(mid), instance=hx(iid),
                               name=MODULE_NAMES.get(mid, "UNKNOWN")))
    c.done()
    return result


def graph_parameters(data, base):
    c, result = Cursor(data, base), []
    while c.pos < len(data):
        offset = c.base + c.pos
        iid, pid, size = c.words(3)
        payload = c.take(size)
        # ACDB graph records have 12-byte headers and 8-byte padded PAYLOADS.
        pad = c.take((-size) % 8)
        if any(pad):
            raise ValueError("nonzero graph padding")
        record = dict(instance=hx(iid), parameter=hx(pid), offset=hx(offset), size=size)
        q = Cursor(payload, offset + 12)
        if pid == 0x08001002:
            record["modules"] = module_list(payload)
        elif pid == 0x08001004:
            record["connections"] = [dict(zip(
                ["source", "source_port", "destination", "destination_port"],
                map(hx, q.words(4)))) for _ in range(q.u32())]
            q.done()
        elif pid == 0x08001061:
            links = []
            for _ in range(q.u32()):
                a, ap, b, bp, n = q.words(5)
                links.append(dict(peer1=hx(a), port1=hx(ap), peer2=hx(b), port2=hx(bp),
                                  properties=properties(q, n)))
            q.done()
            record["control_links"] = links
        elif pid in (0x08001000, 0x08001001, 0x08001003):
            objects = []
            for _ in range(q.u32()):
                instance, count = q.words(2)
                objects.append(dict(instance=hx(instance), properties=properties(q, count)))
            q.done()
            record["objects"] = objects
        result.append(record)
    c.done()
    return result


class Acdb:
    def __init__(self, data):
        if hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
            raise ValueError("ACDB SHA-256 does not match the catalogued REV_0D input")
        if data[:8] != b"ACDB\0\0\0\0":
            raise ValueError("not the pinned ACDB container")
        c = Cursor(data)
        c.take(8)
        if c.u32() != len(data) - 12:
            raise ValueError("invalid container size")
        self.chunks = {}
        while c.pos < len(data):
            name = c.take(4).decode("ascii")
            size = c.u32()
            base = c.pos
            if name in self.chunks:
                raise ValueError("duplicate chunk")
            self.chunks[name] = (base, c.take(size))
        c.done()
        # POOL references point at a length word. Payloads are padded to 4.
        base, pool = self.chunks["POOL"]
        c = Cursor(pool, base)
        self.pool = {}
        while c.pos < len(pool):
            rel = c.pos
            size = c.u32()
            self.pool[rel] = (base + c.pos, c.take(size))
            if any(c.take((-size) % 4)):
                raise ValueError("nonzero POOL padding")
        c.done()

    def lookup(self, name, refs):
        base, data = self.chunks[name]
        c, rows = Cursor(data, base), []
        while c.pos < len(data):
            key_count, count = c.words(2)
            if key_count > 32 or count > len(data) // (4 * (key_count + refs)):
                raise ValueError("invalid lookup counts")
            for _ in range(count):
                offset = c.base + c.pos
                keys, values = c.words(key_count), c.words(refs)
                rows.append((offset, keys, values))
        c.done()
        return rows

    def graphs(self):
        result = []
        for offset, keys, (_, ref) in self.lookup("GKVL", 2):
            base, data = self.pool[ref]
            c, graphs = Cursor(data, base), []
            for _ in range(c.u32()):
                sg, size = c.words(2)
                start = c.base + c.pos
                q = Cursor(c.take(size), start)
                prop_size = q.u32()
                q.take(prop_size)
                param_size = q.u32()
                param_base = q.base + q.pos
                params = graph_parameters(q.take(param_size), param_base)
                q.done()
                graphs.append(dict(subgraph=hx(sg), offset=hx(start), parameters=params))
            c.done()
            if any(g["subgraph"] == "0xb0000001" for g in graphs):
                result.append(dict(lookup_offset=hx(offset), key_values=keys,
                                   pool_offset=hx(base - 4), subgraphs=graphs))
        return result

    def calibration(self):
        de_base, de = self.chunks["CDDE"]
        do_base, do = self.chunks["CDDO"]
        result = []
        for offset, keys, (de_ref, do_ref, _) in self.lookup("CDLU", 3):
            a, b = Cursor(de[de_ref:], de_base + de_ref), Cursor(do[do_ref:], do_base + do_ref)
            count = a.u32()
            if b.u32() != count or count > len(de) // 8:
                raise ValueError("calibration count mismatch")
            for _ in range(count):
                iid, pid = a.words(2)
                base, payload = self.pool[b.u32()]
                if iid not in (0x4001, 0x4024, 0x4026, 0x4027, 0x4028, 0x402B, 0x4157):
                    continue
                item = dict(lookup_offset=hx(offset), key_values=keys, instance=hx(iid),
                            parameter=hx(pid), payload_offset=hx(base), size=len(payload),
                            sha256=hashlib.sha256(payload).hexdigest(), semantics="unknown")
                # These are observations of fields, with their Q interpretation
                # attributed to the earlier report; never treated as deployable tuning.
                if pid == 0x08001510 and len(payload) == 12:
                    w = Cursor(payload).words(3)
                    item.update(channel_count=w[0], reported_q6_temperatures=[v / 64 for v in w[1:]])
                if pid == 0x08001535 and len(payload) == 108:
                    w = Cursor(payload).words(27)
                    item.update(channel_count=w[0], reported_q24_nominal_re=[w[1] / 2**24, w[9] / 2**24])
                result.append(item)
        return result

    def calibration_payloads(self, instances):
        """Raw (instance, parameter, payload) records of the keyless calibration set.

        Windows calibration data: the result goes to private out/ only. Used by
        build-topology/sp11_closedloop.py, which writes the closed-loop supplement.
        """
        de_base, de = self.chunks["CDDE"]
        do_base, do = self.chunks["CDDO"]
        result = []
        for _, keys, (de_ref, do_ref, _) in self.lookup("CDLU", 3):
            if keys:
                continue
            a, b = Cursor(de[de_ref:], de_base + de_ref), Cursor(do[do_ref:], do_base + do_ref)
            count = a.u32()
            if b.u32() != count or count > len(de) // 8:
                raise ValueError("calibration count mismatch")
            for _ in range(count):
                iid, pid = a.words(2)
                _, payload = self.pool[b.u32()]
                if iid in instances:
                    result.append((iid, pid, bytes(payload)))
        return result

    def report(self):
        return dict(schema="sp11-acdb-audit-v1", sha256=EXPECTED_SHA256,
                    deployable=False, reason="parameter semantics and hardware protection unvalidated",
                    chunks={k: dict(offset=hx(v[0]), size=len(v[1])) for k, v in self.chunks.items()},
                    pool_records=len(self.pool), speaker_graph_candidates=self.graphs(),
                    calibration=self.calibration())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("acdb", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = Acdb(args.acdb.read_bytes()).report()
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
