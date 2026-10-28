#!/usr/bin/env python3
"""Derive an ath12k board-2.bin whose entry for this unit carries the Windows board data.

Why: ath12k picks board data by the name
  bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=<id>
inside board-2.bin (sources/linux/drivers/net/wireless/ath/ath12k/core.c:221, :524). This unit
reports qmi-board-id 255 (device log m5-20261028), so Linux loads the generic Qualcomm entry for id
255. The Windows driver builds "bdwlan.elf" for board id 0xff (qcwlanhmt8380.sys, function
0x14014a478 -> 0x140147b80; hardware/wifi/evidence/2026-10-28-windows-board-selection.md). The two
payloads differ. This tool keeps every Fedora entry and replaces only the payload of the entry
named above; the Windows file is a DriverStore blob, so the output stays in out/ and never goes
into git (S5). Staging: firmware worker (request in hardware/wifi/README.md).

Usage (inspect the Fedora file; or build):
  wifi-board2.py list  <board-2.bin[.xz]>
  wifi-board2.py build --fedora <board-2.bin[.xz]> --windows <bdwlan.elf> --out <board-2.bin>
                       [--board-id 255] [--sha256 <expected sha256 of the Windows file>]
  wifi-board2.py selftest <board-2.bin[.xz]>      # re-encode and compare structure and length

Run with python3 -I. No third-party modules.
"""
import argparse
import hashlib
import lzma
import struct
import sys

MAGIC = b"QCA-ATH12K-BOARD\0"
BD_IE_BOARD, BD_IE_REGDB = 0, 1      # drivers/net/wireless/ath/ath12k/hw.h:312-314
BD_NAME, BD_DATA = 0, 1              # hw.h:306-307
NAME_FMT = ("bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,"
            "qmi-chip-id=2,qmi-board-id=%d")


def pad4(n):
    return (n + 3) & ~3


def read(path):
    raw = open(path, "rb").read()
    return lzma.decompress(raw) if path.endswith(".xz") else raw


def parse(d):
    """-> (header, ies). header = magic plus its padding, kept byte for byte (Fedora's padding is not zero)."""
    if not d.startswith(MAGIC):
        sys.exit("not an ath12k board file (magic)")
    off = pad4(len(MAGIC))
    header = d[:off]
    ies = []                         # [(top_id, [(sub_id, payload), ...])]
    while off + 8 <= len(d):
        tid, tlen = struct.unpack_from("<II", d, off)
        off += 8
        body = d[off:off + tlen]
        off += pad4(tlen)
        subs, o = [], 0
        while o + 8 <= len(body):
            sid, slen = struct.unpack_from("<II", body, o)
            o += 8
            subs.append((sid, body[o:o + slen]))
            o += pad4(slen)
        ies.append((tid, subs))
    return header, ies


def encode(header, ies):
    out = bytearray(header)
    for tid, subs in ies:
        body = bytearray()
        for sid, payload in subs:
            body += struct.pack("<II", sid, len(payload)) + payload + b"\0" * (pad4(len(payload)) - len(payload))
        out += struct.pack("<II", tid, len(body)) + body + b"\0" * (pad4(len(body)) - len(body))
    return bytes(out)


def groups(ies):
    """Yield (top_id, [names], data). In one top-level IE a data element belongs to every name element
    before it (core.c:313-365: a match on any earlier name selects the next data)."""
    for tid, subs in ies:
        names = []
        for sid, payload in subs:
            if sid == BD_NAME:
                names.append(payload.decode())
            elif sid == BD_DATA:
                yield tid, names, payload
                names = []


def cmd_list(a):
    d = read(a.file)
    print("sha256(decompressed)", hashlib.sha256(d).hexdigest(), "len", len(d))
    for tid, names, data in groups(parse(d)[1]):
        kind = "BOARD" if tid == BD_IE_BOARD else "REGDB" if tid == BD_IE_REGDB else "IE%d" % tid
        for n in names:
            print(kind, n, len(data), hashlib.sha256(data).hexdigest()[:12])


def cmd_selftest(a):
    d = read(a.file)
    # Fedora's padding bytes are not zero, so compare structure and length, not bytes
    e = encode(*parse(d))
    ok = len(e) == len(d) and parse(e) == parse(d)
    print("re-encode keeps every element and the length:", ok)
    sys.exit(0 if ok else 1)


def cmd_build(a):
    d = read(a.fedora)
    win = open(a.windows, "rb").read()
    got = hashlib.sha256(win).hexdigest()
    if a.sha256 and got != a.sha256:
        sys.exit("Windows file sha256 %s != expected %s" % (got, a.sha256))
    if win[:4] != b"\x7fELF":
        sys.exit("Windows board file is not an ELF (it must be the bdwlan*.elf container)")
    target = NAME_FMT % a.board_id
    header, ies = parse(d)
    shadowed = [h for h in groups(ies) if h[0] == BD_IE_BOARD and target in h[1]]
    # The first matching top-level IE wins (core.c:430-470), so a new IE in front shadows Fedora's
    # entry of that name without touching the other names that share its payload.
    ies.insert(0, (BD_IE_BOARD, [(BD_NAME, target.encode()), (BD_DATA, win)]))
    out = encode(header, ies)
    assert encode(*parse(out)) == out
    open(a.out, "wb").write(out)
    print("wrote %s: %d bytes, shadowed fedora entries=%d, windows sha256 %s, name %s"
          % (a.out, len(out), len(shadowed), got, target))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("list"); s.add_argument("file"); s.set_defaults(f=cmd_list)
    s = sp.add_parser("selftest"); s.add_argument("file"); s.set_defaults(f=cmd_selftest)
    s = sp.add_parser("build")
    s.add_argument("--fedora", required=True); s.add_argument("--windows", required=True)
    s.add_argument("--out", required=True); s.add_argument("--board-id", type=int, default=255)
    s.add_argument("--sha256"); s.set_defaults(f=cmd_build)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
