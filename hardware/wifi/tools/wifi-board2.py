#!/usr/bin/env python3
"""Derive an ath12k board-2.bin whose entry for this unit carries the Windows board data.

Why: ath12k picks board data by the name
  bus=pci,vendor=17cb,device=1107,subsystem-vendor=17cb,subsystem-device=1107,qmi-chip-id=2,qmi-board-id=<id>
inside board-2.bin (sources/linux/drivers/net/wireless/ath/ath12k/core.c:221, :524). This unit
reports qmi-board-id 255 (device log m5-20261028), so Linux loads the generic Qualcomm entry for id
255. The Windows driver builds "bdwlan.elf" for board id 0xff (qcwlanhmt8380.sys, function
0x14014a478 -> 0x140147b80; hardware/wifi/evidence/2026-10-28-windows-board-selection.md). The two
payloads differ. This tool keeps every Fedora entry and prepends a shadow entry for the
name above; the Windows file is a DriverStore blob, so the output stays in out/ and never goes
into git (S5). Staging: operator-provided image input (F2/I7 in hardware/wifi/README.md).

Usage (inspect the Fedora file; or build):
  wifi-board2.py list  <board-2.bin[.xz]>
  wifi-board2.py build --fedora <board-2.bin[.xz]> --windows <bdwlan.elf> --out <board-2.bin>
                       [--board-id 255] [--sha256 <Windows SHA-256>]
                       [--fedora-sha256 <decompressed Fedora SHA-256>]
  wifi-board2.py selftest <board-2.bin[.xz]>      # re-encode and compare structure and length
  wifi-board2.py verify <board-2.bin> [--fedora <board-2.bin[.xz]>] [--board-id 255] [--sha256 <Windows SHA-256>]
                                                  # parse back; exit 0 only if well-formed (see cmd_verify)

verify and build checks are structural only. They cannot show that the firmware accepts the payload:
the M10 private image passed them and the WCN7850 firmware still crashed (MHI_CB_EE_RDDM) after
board data was selected; see evidence/2026-10-30-m10-board-crash.md. Image rule: install the derived
file only if verify exits 0, otherwise keep Fedora's generic file.

Run with python3 -I. No third-party modules.
"""
import argparse
import hashlib
import lzma
import os
from pathlib import Path
import struct
import sys
import tempfile

WINDOWS_SHA256 = "b24438910ff0383d299798a997d3ef3484be624ac013aec2ce7939ec32900c4f"
FEDORA_SHA256 = "6a98237c743d864773a547e81e23f0c6dc721dcd7331926bee7381e2152e00fd"
LOCAL_OUT = Path(__file__).resolve().parents[3] / "out"

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
    while off < len(d):
        if off + 8 > len(d):
            sys.exit("truncated top-level IE header")
        tid, tlen = struct.unpack_from("<II", d, off)
        off += 8
        if off + pad4(tlen) > len(d):
            sys.exit("truncated top-level IE body")
        body = d[off:off + tlen]
        off += pad4(tlen)
        subs, o = [], 0
        while o < len(body):
            if o + 8 > len(body):
                sys.exit("truncated nested IE header")
            sid, slen = struct.unpack_from("<II", body, o)
            o += 8
            if o + pad4(slen) > len(body):
                sys.exit("truncated nested IE body")
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


BOARD_SIZE_MAX = 256 * 1024          # wifi7/hw.c:455 fw.board_size; ath12k truncates larger payloads


def check_elf(p):
    """Return an error string, or None if p is a well-formed 32-bit LE ELF whose segments fit in p."""
    if len(p) < 52 or p[:4] != b"\x7fELF":
        return "payload is not an ELF"
    if p[4] != 1 or p[5] != 1:
        return "not ELF32 little endian"
    phoff, = struct.unpack_from("<I", p, 28)
    phentsize, phnum = struct.unpack_from("<HH", p, 42)
    if phnum == 0 or phentsize != 32 or phoff + phnum * phentsize > len(p):
        return "program header table outside payload"
    for i in range(phnum):
        _t, off, _va, _pa, filesz, _msz, _fl, _al = struct.unpack_from("<8I", p, phoff + i * phentsize)
        if off + filesz > len(p):
            return "segment %d outside payload" % i
    return None


def verify(path, fedora=None, board_id=255, win_sha=None):
    """Parse a derived board-2.bin back. Returns a list of problems (empty = well-formed)."""
    errs = []
    d = read(path)
    try:
        header, ies = parse(d)               # exits on truncated headers/bodies
    except SystemExit as e:
        return ["malformed IE structure: %s" % e]
    if encode(header, ies) != d and len(encode(header, ies)) != len(d):
        errs.append("re-encoded length differs")
    seen_names = set()
    first_board = None
    for tid, names, data in groups(ies):
        if tid not in (BD_IE_BOARD, BD_IE_REGDB):
            errs.append("unknown top-level IE %d" % tid)
        if not names:
            errs.append("data element without a name element")
        if tid == BD_IE_BOARD:
            if len(data) > BOARD_SIZE_MAX:
                errs.append("board payload %d B exceeds board_size" % len(data))
            e = check_elf(data)
            if e:
                errs.append("board payload for %s: %s" % (names[:1], e))
            if first_board is None:
                first_board = (names, data)
        for n in names:
            seen_names.add((tid, n))
    if not any(t == BD_IE_REGDB for t, _ in seen_names):
        errs.append("no REGDB entry")
    target = NAME_FMT % board_id
    if first_board is None or target not in first_board[0]:
        errs.append("first BOARD entry is not the target name")
    elif win_sha and hashlib.sha256(first_board[1]).hexdigest() != win_sha:
        errs.append("first BOARD payload is not the expected Windows file")
    if fedora:
        fed = {(t, n) for t, ns, _ in groups(parse(read(fedora))[1]) for n in ns}
        if not fed <= seen_names:
            errs.append("%d Fedora names missing" % len(fed - seen_names))
    return errs


def cmd_verify(a):
    errs = verify(a.file, a.fedora, a.board_id, a.sha256)
    for e in errs:
        print("FAIL:", e)
    print("verify:", "FAIL" if errs else "OK (structure only; firmware acceptance is not tested)")
    sys.exit(1 if errs else 0)


def cmd_build(a):
    output = Path(a.out).resolve()
    if not output.is_relative_to(LOCAL_OUT.resolve()):
        sys.exit("derived board file must stay under this repository out/ (S5)")
    if output in (Path(a.fedora).resolve(), Path(a.windows).resolve()):
        sys.exit("output must not overwrite either input")
    d = read(a.fedora)
    if hashlib.sha256(d).hexdigest() != a.fedora_sha256:
        sys.exit("Fedora board file hash differs from the pinned decompressed input")
    win = open(a.windows, "rb").read()
    got = hashlib.sha256(win).hexdigest()
    if got != a.sha256:
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
    if parse(out) != (header, ies):
        sys.exit("derived file did not preserve every parsed element")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write(out)
            f.flush()
            os.fsync(f.fileno())
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    errs = verify(str(output), a.fedora, a.board_id, got)
    if errs:
        output.unlink()
        sys.exit("derived file failed verification, removed: " + "; ".join(errs))
    print("verify: OK (structure only; M10 showed firmware can still crash, see evidence 2026-10-30)")
    print("sha256(output)", hashlib.sha256(out).hexdigest())
    print("wrote %s: %d bytes, shadowed fedora entries=%d, windows sha256 %s, name %s"
          % (a.out, len(out), len(shadowed), got, target))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("list"); s.add_argument("file"); s.set_defaults(f=cmd_list)
    s = sp.add_parser("selftest"); s.add_argument("file"); s.set_defaults(f=cmd_selftest)
    s = sp.add_parser("verify"); s.add_argument("file"); s.add_argument("--fedora")
    s.add_argument("--board-id", type=int, default=255); s.add_argument("--sha256")
    s.set_defaults(f=cmd_verify)
    s = sp.add_parser("build")
    s.add_argument("--fedora", required=True); s.add_argument("--windows", required=True)
    s.add_argument("--out", required=True); s.add_argument("--board-id", type=int, default=255)
    s.add_argument("--sha256", default=WINDOWS_SHA256)
    s.add_argument("--fedora-sha256", default=FEDORA_SHA256,
                   help="expected SHA-256 of decompressed Fedora board file (default: 20261019)")
    s.set_defaults(f=cmd_build)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
