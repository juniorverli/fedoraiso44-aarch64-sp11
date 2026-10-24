#!/usr/bin/env python3
"""Read the catalogued Windows GPU configuration as data, without disassembly.

Run from the project root. Prints only the named graphics clock table, its
offsets and the input digest. The record interpretation is documented in the
speed-bin evidence; this is not a general Qualcomm configuration decoder.
"""

import csv
import hashlib
import struct
from pathlib import Path


def records(blob, start, end):
    result = []
    while start < end:
        if end - start < 4:
            raise ValueError(f"short record at {start:#x}")
        offset = start
        kind, size = struct.unpack_from("<HH", blob, start)
        start += 4
        if start + size > end:
            raise ValueError(f"record outside parent at {offset:#x}")
        payload = blob[start:start + size]
        if kind == 0 and size == 8:
            value = int.from_bytes(payload, "little")
        elif kind == 1 and payload.endswith(b"\0"):
            value = payload[:-1].decode("ascii")
        elif kind == 3:
            value = records(blob, start, start + size)
        else:
            raise ValueError(f"unsupported record at {offset:#x}: {kind}/{size}")
        result.append((offset, kind, value))
        start += size
    return result


def clock_table(blob):
    marker = b"\x01\x00\x12\x00ENGINE_PSTATE_SET\0"
    offset = 0
    matches = []
    while (offset := blob.find(marker, offset)) >= 0:
        parent = offset - 4
        kind, size = struct.unpack_from("<HH", blob, parent)
        if kind != 3 or parent + 4 + size > len(blob):
            raise ValueError(f"invalid parent at {parent:#x}")
        children = records(blob, parent + 4, parent + 4 + size)
        labels = [value for _, kind, value in children if kind == 1]
        if labels[:3] == ["ENGINE_PSTATE_SET", "GRAPHICS_FREQ_CONTROL", "CORE_CLOCK"]:
            matches.append((parent, children))
        offset += len(marker)
    if len(matches) != 1:
        raise ValueError(f"expected one graphics core clock table, got {len(matches)}")
    return matches[0]


def main():
    with Path("sources/binary-catalog.tsv").open() as catalog:
        inputs = [r for r in csv.DictReader(catalog, delimiter="\t")
                  if Path(r["path"]).name.startswith("qcdxkmbase8380")
                  and r["path"].endswith(".bin")]
    if not inputs:
        raise ValueError("no matching catalog entries")
    for entry in inputs:
        if entry["kind"] != "data":
            raise ValueError(f"not catalogued as data: {entry['path']}")
        blob = (Path("sources/windows") / entry["path"]).read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != entry["sha256"]:
            raise ValueError(f"catalog digest mismatch: {entry['path']}")
        parent, children = clock_table(blob)
        print(f"{entry['path']}\nsha256={digest} package={parent:#x}")
        count = children[4][2]
        rows = [value for _, kind, value in children if kind == 3]
        if count != len(rows):
            raise ValueError("declared PSTATE count mismatch")
        for row in rows:
            if len(row) != 6 or row[0][2] != "PSTATE":
                raise ValueError("unexpected PSTATE layout")
            index, frequency = row[1], row[2]
            print(f"  state={index[2]:2} value={frequency[2]:10} "
                  f"payload_offset={frequency[0] + 4:#x}")


if __name__ == "__main__":
    main()
