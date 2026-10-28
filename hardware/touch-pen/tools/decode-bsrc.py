#!/usr/bin/env python3
"""Validate catalogued BSRC ACPI data and print only SP11 GPIO policy.

Run from the project root. No disassembly, writes or binary exports.
The record layout is ACPI_METHOD_ARGUMENT: u16 type, u16 data length,
then max(4, length) bytes, without inter-record padding in these files.
"""

import hashlib
from pathlib import Path
import struct


PACKAGE = Path("sources/windows/DriverStore/qcspi8380.inf_arm64_14b48dd9d115a472")
EXPECTED = {
    "BSRC_SPI.bin": "4ce2d0fba6560f544198bfb5de4c3c33ae9d8527a66e5468379a161524926443",
    "BSRC_QSPI.bin": "b06b6f0a26652f1187bc12e347c53e8a51ef25c47b82cd403c9b73f64e48d11a",
}


def argument(data, offset, end):
    if offset + 4 > end:
        raise ValueError(f"truncated argument at {offset:#x}")
    kind, length = struct.unpack_from("<HH", data, offset)
    start = offset + 4
    stop = start + max(4, length)
    if stop > end:
        raise ValueError(f"argument exceeds parent at {offset:#x}")
    payload = data[start:start + length]
    if kind == 0:
        if length != 8:
            raise ValueError(f"unexpected integer size at {offset:#x}")
        value = int.from_bytes(payload, "little")
    elif kind == 1:
        if not payload.endswith(b"\0"):
            raise ValueError(f"unterminated string at {offset:#x}")
        value = payload[:-1].decode("ascii")
    elif kind == 2:
        value = f"buffer ({length} bytes, omitted)"
    elif kind == 3:
        value = []
        cursor = start
        while cursor < start + length:
            child, cursor = argument(data, cursor, start + length)
            value.append(child)
        if cursor != start + length:
            raise ValueError(f"package boundary mismatch at {offset:#x}")
    else:
        raise ValueError(f"unknown type {kind} at {offset:#x}")
    return (offset, value), stop


def values(node):
    value = node[1]
    return [values(child) for child in value] if isinstance(value, list) else value


def show_gpio(node, parents=()):
    offset, value = node
    if not isinstance(value, list):
        return
    labels = tuple(str(child[1]) for child in value if not isinstance(child[1], list))
    if labels and labels[0] == "TLMMGPIO":
        print(f"  package={offset:#06x}", "/".join(parents), values(node))
    for child in value:
        show_gpio(child, parents + labels)


def main():
    for name, expected in EXPECTED.items():
        path = PACKAGE / name
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected:
            raise ValueError(f"catalog hash mismatch: {path}")
        signature, total, count = struct.unpack_from("<4sII", data)
        if signature != b"AeoB" or total != len(data):
            raise ValueError(f"invalid ACPI_EVAL_OUTPUT_BUFFER: {path}")
        roots = []
        cursor = 12
        while cursor < total:
            root, cursor = argument(data, cursor, total)
            roots.append(root)
        if cursor != total or len(roots) != count:
            raise ValueError(f"root count/size mismatch: {path}")
        print(path, "sha256=" + digest, f"validated={count} roots/{total} bytes")
        found = []
        for root in roots:
            value = values(root)
            if isinstance(value, list) and value[:2] == ["DEVICE", "\\_SB.SP11"]:
                found.append(root)
        if len(found) != 1:
            raise ValueError(f"expected exactly one SP11 policy: {path}")
        show_gpio(found[0])


if __name__ == "__main__":
    main()
