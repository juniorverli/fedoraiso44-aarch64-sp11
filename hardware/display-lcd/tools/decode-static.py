#!/usr/bin/env python3
"""Reproduce selected display facts without disassembly or private identifiers.

Run from the project root. Binary inputs remain under sources/; only selected
configuration values, timing fields and input hashes are printed.
"""

import hashlib
from pathlib import Path
import struct


WINDOWS = Path("sources/windows")
EXTENSION = WINDOWS / "DriverStore/surface_dxext_8380.inf_arm64_69910c8aa1a39011"


def read_input(path):
    data = path.read_bytes()
    print(path, "SHA-256", hashlib.sha256(data).hexdigest())
    return data


def argument(data, offset, end):
    """Decode packed ACPI_METHOD_ARGUMENT records, retaining source offsets."""
    kind, length = struct.unpack_from("<HH", data, offset)
    start = offset + 4
    stop = start + max(length, 4)
    assert stop <= end, (offset, kind, length, end)
    payload = data[start:start + length]
    if kind == 0:
        assert length == 8
        value = int.from_bytes(payload, "little")
    elif kind == 1:
        assert payload.endswith(b"\0")
        value = payload[:-1].decode("ascii")
    elif kind == 2:
        value = f"buffer ({length} bytes, omitted)"
    else:
        assert kind == 3, (offset, kind)
        value = []
        cursor = start
        while cursor < stop:
            child, cursor = argument(data, cursor, stop)
            value.append(child)
        assert cursor == stop
    return (offset, value), stop


def values(node):
    value = node[1]
    return [values(child) for child in value] if isinstance(value, list) else value


def selected_records(node, parents=()):
    offset, value = node
    if not isinstance(value, list):
        return
    labels = tuple(child[1] for child in value if isinstance(child[1], str))
    if any(label in ("PMICGPIO", "TLMMGPIO", "DELAY") for label in labels):
        print(f"  {offset:#x}", "/".join(parents[-6:]), values(node))
    for child in value:
        selected_records(child, parents + labels)


def decode_blob(name):
    data = read_input(EXTENSION / f"qcdxkmext8380_{name}.bin")
    header_size, magic, revision, count, name_size = struct.unpack_from("<5I", data)
    assert (header_size, magic, revision) == (52, 0x80807070, 1)
    assert count == 10 and name_size == 12
    assert data[20:32] == b"8380_DEN_EXT"
    previous_end = header_size + count * 12
    for index in range(count):
        method, offset, size = struct.unpack_from("<4sII", data, header_size + index * 12)
        assert offset == previous_end and offset + size <= len(data)
        previous_end = offset + size
        signature, output_size, output_count = struct.unpack_from("<4sII", data, offset)
        assert signature == b"AeoB" and size == output_size
        print(f"{name} {method.decode()}: offset={offset:#x}, length={size}, count={output_count}")
        cursor = offset + 12
        roots = []
        while cursor < offset + size:
            node, cursor = argument(data, cursor, offset + size)
            roots.append(node)
        assert cursor == offset + size and len(roots) == output_count
        # G0MD contains the GPU rail/pin transition; other blocks are validated
        # structurally but deliberately not printed as complete binary dumps.
        if method == b"G0MD":
            for node in roots:
                selected_records(node)
    assert previous_end == len(data)


def decode_edid():
    data = read_input(WINDOWS / "live-inventory/panel/edid-LGD077B.bin")
    assert len(data) == 384 and data[:8] == b"\0\xff\xff\xff\xff\xff\xff\0"
    assert data[126] == 1 and not any(data[256:])
    assert all(sum(data[n:n + 128]) % 256 == 0 for n in (0, 128, 256))
    assert sum(data[129:255]) % 256 == 0
    print("EDID: 256 declared bytes; 128 trailing zero bytes; all checksums valid")
    print("EDID input byte:", hex(data[20]), "(10 bpc, DisplayPort)")
    assert data[128:133] == bytes((0x70, 0x20, 0x79, 0x02, 0))
    cursor = 133
    while cursor < 254:
        if not any(data[cursor:254]):
            print(f"DisplayID padding: {254 - cursor} bytes at {cursor:#x}")
            cursor = 254
            break
        tag, revision, length = data[cursor:cursor + 3]
        block = data[cursor + 3:cursor + 3 + length]
        print(f"DisplayID block {tag:#x}, revision={revision}, length={length}, offset={cursor:#x}")
        if tag == 0x22:
            assert length == 40
            for index in range(2):
                timing = block[index * 20:(index + 1) * 20]
                clock_khz = int.from_bytes(timing[:3], "little") + 1
                fields = struct.unpack_from("<8H", timing, 4)
                counts = [(n & (0x7fff if i in (2, 6) else 0xffff)) + 1
                          for i, n in enumerate(fields)]
                ha, hb, hf, hs, va, vb, vf, vs = counts
                ht, vt = ha + hb, va + vb
                print(f"  offset={cursor + 3 + index * 20:#x}, clock={clock_khz} kHz, "
                      f"preferred={bool(timing[3] & 0x80)}, refresh={clock_khz * 1000 / ht / vt:.9f}")
                print("  horizontal:", ha, ha + hf, ha + hf + hs, ht,
                      "porches:", hf, hs, hb - hf - hs,
                      "positive:", bool(fields[2] & 0x8000))
                print("  vertical:", va, va + vf, va + vf + vs, vt,
                      "porches:", vf, vs, vb - vf - vs,
                      "positive:", bool(fields[6] & 0x8000))
        cursor += 3 + length
    assert cursor == 254


if __name__ == "__main__":
    decode_edid()
    decode_blob("DENidp")
    decode_blob("DENcrd")
