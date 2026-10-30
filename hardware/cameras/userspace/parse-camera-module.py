#!/usr/bin/env python3
"""Read the Windows camera sensor module data of the Surface Pro 11 (structure only).

Reads 'QTI Chromatix' sensor module files (com.surface.sensormodule.*.bin, parser
"Parameter Parser V3.4.0") from the Windows DriverStore on this machine and prints
only their STRUCTURE: container checks, symbol, mode and record counts, field widths,
operation histograms. It never prints a register address or value.

    python3 -I parse-camera-module.py                    # all three sensors
    python3 -I parse-camera-module.py rear front         # chosen sensors
    python3 -I parse-camera-module.py --file PATH        # any module file
    python3 -I parse-camera-module.py --emit DIR         # also write raw records

--emit DIR writes one SPMODREC v1 file per sensor (format below) under DIR. The files
carry Windows vendor register data (risk S5): DIR must be outside the git tree, or
inside it only if git ignores it (the repository's /out). It is meant for
out/firmware-private/cameras/ and must never be committed or published. The tool
refuses any other directory inside a git work tree.

Windows data: sources/windows/DriverStore (not in git). The default search root is
<repo>/sources/windows, found from this script's location; --windows-dir overrides.

Container (all little endian; "Chromatix", verified on the three modules):
  0x00 char[28]  'QTI Chromatix Header' padded with NUL
  0x1c u32       file size minus 4 (CRC word excluded)
  0x20 u32 3, 0x24 u32 1   container version words (constant in all files)
  0x28 char[48]  parser version string; 0x58 char[64] module name
  0xa0 u32 section table offset (0xa8), 0xa4 u32 section count (3)
  section table: {u32 id, u32 file_offset, u32 size} x count
     id 0 symbol table: 0x38-byte records {u32 index, char[32] name, i32 a, i32 b,
          i32 c, u32 data_offset, u32 data_size}; index is 1-based, in file order
     id 1 data heap: each symbol's bytes at section_offset + data_offset
     id 2 trailer: 0x14 bytes
  last 4 bytes: zlib CRC-32 of every byte before them
Objects are stored as packed little endian structs; a variable-length member is a
(u32 count, u32 symbol index) pair, an array is the bytes of its symbol.

SPMODREC v1 (output of --emit; every field little endian):
  header, 48 bytes
     0 char[8] magic 'SPMODREC'
     8 u16 version (1)       10 u16 header_size (48)
    12 u32 total_size        16 u32 crc32 of [header_size, total_size)
    20 u16 n_modes           22 u16 sensor_index (0 rear, 1 front, 2 IR; PCFG order)
    24 u32 cfa_code (raw colour filter code of the module, see evidence)
    28 u32 reserved (0)
    32 char[16] sensor name (NUL padded, from the module)
  sequence table, 5 entries of {u32 offset, u32 count} right after the header, in
  this order: init, stream_on, stream_off, group_hold_on, group_hold_off
  mode table, n_modes records of 56 bytes, right after the sequence table:
     0 u16 width        2 u16 height       4 u32 fps_milli (frames/s x 1000)
     8 u8 lanes (D-PHY lanes or C-PHY trios)   9 u8 cphy (0 D-PHY, 1 C-PHY)
    10 u8 bits_per_pixel  11 u8 mipi_data_type (0x2b RAW10)  12 u8 virtual_channel
    13 u8 cfa_code      14 u16 reserved
    16 u32 pixel_clock_hz (output pixel clock of the module)
    20 u32 lane_rate_kbps (pixel_clock * bits / lanes / 1000: bit/s per lane for
          D-PHY, bit/s per trio before the 7/16 symbol conversion for C-PHY)
    24 u32 line_length (module unit)   28 u32 frame_length_lines
    32 u32 min_vblank  36 u32 min_hblank
    40 u32 mbus_code (MEDIA_BUS_FMT_*; 0 = unresolved, see --bayer)
    44 u32 ops_offset  48 u32 ops_count   52 u32 reserved (0)
  record (20 bytes), used by every sequence:
     0 u32 reg_address   4 u32 data (the single value; for a read, the length)
     8 u32 delay_us      12 u8 op (0 write, 3 read, 4 poll-until-equal; raw module code)
    13 u8 addr_bytes (register address width in bytes)  14 u8 data_bytes
    15 u8 flags (bit0: slave_override valid)   16 u16 slave_override (8-bit form)
    18 u16 reserved (0)
  offsets count from the start of the file.
"""
import argparse
import glob
import os
import struct
import subprocess
import sys
import zlib

MAGIC = b"QTI Chromatix Header"
SYM_SIZE = 0x38
REG_SIZE = 40
RES_SIZE = 252
SEQ_ROOT = {  # (count, symbol) pairs inside sensorDriverData
    "stream_on": 0x168,
    "stream_off": 0x170,
    "group_hold_on": 0x178,
    "group_hold_off": 0x180,
}
INIT_PAIR = 0x1A8  # (count, symbol of initSettings)
SEQ_ORDER = ["init", "stream_on", "stream_off", "group_hold_on", "group_hold_off"]
ADDR_BYTES = {1: 1, 2: 2, 3: 3, 4: 4}
BAYER = {"bggr": 0x3007, "gbrg": 0x300E, "grbg": 0x300A, "rggb": 0x300F}
Y10 = 0x200A

SENSORS = {
    "rear": ("surfacecamrearsensor_extension8380.inf_arm64_*",
             "com.surface.sensormodule.rfc_ov13858.bin", 0, "ov13858"),
    "front": ("surfacecamfrontsensor_extension8380.inf_arm64_*",
              "com.surface.sensormodule.ffc_imx681.bin", 1, "imx681"),
    "ir": ("surfacecamauxsensor_extension8380.inf_arm64_*",
           "com.surface.sensormodule.aux_vd55g0_MSHW0492.bin", 2, "vd55g0"),
}


class FormatError(Exception):
    pass


def u32(b, o):
    if o < 0 or o + 4 > len(b):
        raise FormatError("read outside the file at 0x%x" % o)
    return struct.unpack_from("<I", b, o)[0]


class Module:
    def __init__(self, path):
        self.path = path
        b = self.b = open(path, "rb").read()
        if len(b) < 0xD0 or b[: len(MAGIC)] != MAGIC:
            raise FormatError("not a QTI Chromatix file")
        if u32(b, 0x1C) != len(b) - 4:
            raise FormatError("size field does not match the file size")
        self.crc_ok = zlib.crc32(b[:-4]) & 0xFFFFFFFF == u32(b, len(b) - 4)
        if not self.crc_ok:
            raise FormatError("CRC-32 trailer mismatch")
        self.version_words = (u32(b, 0x20), u32(b, 0x24))
        self.parser = b[0x28:0x58].split(b"\0")[0].decode("latin1")
        self.name = b[0x58:0x98].split(b"\0")[0].decode("latin1")
        to, n = u32(b, 0xA0), u32(b, 0xA4)
        if n < 2 or n > 8:
            raise FormatError("unexpected section count %d" % n)
        self.secs = []
        for i in range(n):
            sid, off, size = struct.unpack_from("<III", b, to + 12 * i)
            if off + size > len(b) - 4:
                raise FormatError("section %d outside the file" % sid)
            self.secs.append((sid, off, size))
        sec = {s[0]: s for s in self.secs}
        if 0 not in sec or 1 not in sec:
            raise FormatError("symbol or data section missing")
        _, so, ss = sec[0]
        _, do, ds = sec[1]
        self.syms = []
        self.by = {}
        for i in range(ss // SYM_SIZE):
            o = so + i * SYM_SIZE
            idx = u32(b, o)
            name = b[o + 4:o + 36].split(b"\0")[0].decode("latin1")
            a, bb, c, doff, dsz = struct.unpack_from("<iiiII", b, o + 36)
            if doff + dsz > ds:
                raise FormatError("symbol %d data outside the data section" % idx)
            s = dict(idx=idx, name=name, a=a, b=bb, c=c, doff=doff, dsz=dsz, foff=do + doff)
            if idx != i + 1 or idx in self.by:
                raise FormatError("symbol indices are not 1..N in order")
            self.syms.append(s)
            self.by[idx] = s

    def sym(self, idx):
        if idx not in self.by:
            raise FormatError("dangling symbol index %d" % idx)
        return self.by[idx]

    def data(self, idx):
        s = self.sym(idx)
        return self.b[s["foff"]:s["foff"] + s["dsz"]]

    def named(self, name):
        return [s for s in self.syms if s["name"] == name]

    def regs(self, idx, expect=None):
        """Decode a regSetting array. Returns a list of dict records."""
        s = self.sym(idx)
        if s["name"] != "regSetting" or s["dsz"] % REG_SIZE:
            raise FormatError("symbol %d is not a regSetting array" % idx)
        if expect is not None and expect != s["dsz"] // REG_SIZE:
            raise FormatError("regSetting count mismatch on symbol %d" % idx)
        out = []
        for i in range(s["dsz"] // REG_SIZE):
            f = struct.unpack_from("<10I", self.b, s["foff"] + REG_SIZE * i)
            slave = None
            if f[0]:
                sd = self.data(f[1])
                if len(sd) not in (1, 2, 4):
                    raise FormatError("odd slave address symbol size")
                slave = int.from_bytes(sd, "little")
            if f[3] != 1:
                raise FormatError("register data count %d: bursts unsupported" % f[3])
            rd = self.data(f[4])
            if len(rd) < 4:
                raise FormatError("register data symbol too small")
            delay = 0
            if f[8]:
                dd = self.data(f[9])
                if len(dd) >= 4:
                    delay = struct.unpack_from("<I", dd)[0]
            out.append(dict(slave=slave, addr=f[2], data=struct.unpack_from("<I", rd)[0],
                            addr_type=f[5], data_type=f[6], op=f[7], delay_us=delay))
        return out

    def pair(self, blob, off):
        return struct.unpack_from("<II", blob, off)

    def root(self):
        r = self.named("sensorDriverData")
        if len(r) != 1:
            raise FormatError("expected exactly one sensorDriverData")
        return self.data(r[0]["idx"])

    def sequence(self, key):
        root = self.root()
        if key == "init":
            cnt, sym = self.pair(root, INIT_PAIR)
            recs = []
            if not cnt:
                return recs
            blob = self.data(sym)
            if self.sym(sym)["name"] != "initSettings" or len(blob) != 12 * cnt:
                raise FormatError("initSettings layout")
            for i in range(cnt):
                _kind, n, isym = struct.unpack_from("<III", blob, 12 * i)
                ib = self.data(isym)
                if self.sym(isym)["name"] != "initSetting" or len(ib) != 8 * n:
                    raise FormatError("initSetting layout")
                for j in range(n):
                    c2, rsym = struct.unpack_from("<II", ib, 8 * j)
                    recs += self.regs(rsym, c2)
            return recs
        cnt, sym = self.pair(root, SEQ_ROOT[key])
        return self.regs(sym, cnt) if cnt else []

    def modes(self):
        rd = self.named("resolutionData")
        if len(rd) != 1:
            raise FormatError("expected one resolutionData")
        blob = self.data(rd[0]["idx"])
        if len(blob) % RES_SIZE:
            raise FormatError("resolutionData size is not a multiple of %d" % RES_SIZE)
        modes = []
        for m in range(len(blob) // RES_SIZE):
            e = blob[m * RES_SIZE:(m + 1) * RES_SIZE]
            g = lambda o: struct.unpack_from("<I", e, o)[0]
            sc_n, sc_sym = g(0x14), g(0x18)
            rs_n, rs_sym = g(0x6C), g(0x70)
            if sc_n != 1 or rs_n != 1:
                raise FormatError("mode %d: expected one stream configuration and one resSettings" % m)
            sc = self.data(sc_sym)
            if self.sym(sc_sym)["name"] != "streamConfiguration" or len(sc) != 60:
                raise FormatError("mode %d: streamConfiguration layout" % m)
            sf = struct.unpack("<15I", sc)
            rs = self.data(rs_sym)
            if self.sym(rs_sym)["name"] != "resSettings" or len(rs) != 8:
                raise FormatError("mode %d: resSettings layout" % m)
            rcount, rsym = struct.unpack("<II", rs)
            recs = self.regs(rsym, rcount)
            fps = struct.unpack_from("<d", e, 0x40)[0]
            modes.append(dict(
                index=m, cfa=g(0x10), line_length=g(0x24), frame_length=g(0x28),
                min_hblank=g(0x2C), min_vblank=g(0x30), pixel_clock=g(0x34), fps=fps,
                lanes=g(0x50), cphy=g(0x60),
                vc_sym=sf[1], data_type=sf[2], width=sf[5], height=sf[6], bits=sf[7],
                records=recs))
        return modes


def lane_rate_kbps(m):
    if not m["lanes"]:
        return 0
    return m["pixel_clock"] * m["bits"] // m["lanes"] // 1000


def op_hist(recs):
    h = {}
    for r in recs:
        h[r["op"]] = h.get(r["op"], 0) + 1
    return h


def describe(mod, label):
    p = print
    p("== %s: %s" % (label, os.path.basename(mod.path)))
    p("  container: parser '%s', module '%s', version words %s, sections %s, CRC-32 ok"
      % (mod.parser, mod.name, mod.version_words, [(s[0], s[2]) for s in mod.secs]))
    names = {}
    for s in mod.syms:
        names[s["name"]] = names.get(s["name"], 0) + 1
    p("  symbols: %d total, %d distinct names, %d with data"
      % (len(mod.syms), len(names), sum(1 for s in mod.syms if s["dsz"])))
    arrays = [s for s in mod.syms if s["name"] == "regSetting" and s["dsz"]]
    p("  regSetting arrays: %d, records %d, element size %d bytes"
      % (len(arrays), sum(s["dsz"] // REG_SIZE for s in arrays), REG_SIZE))
    allrecs = [r for s in arrays for r in mod.regs(s["idx"])]
    p("  record kinds: addr_type codes %s, data_type codes %s, op codes %s, slave override on %d, delay non-zero on %d"
      % (sorted({r["addr_type"] for r in allrecs}), sorted({r["data_type"] for r in allrecs}),
         sorted({r["op"] for r in allrecs}), sum(1 for r in allrecs if r["slave"] is not None),
         sum(1 for r in allrecs if r["delay_us"])))
    for key in SEQ_ORDER:
        seq = mod.sequence(key)
        p("  sequence %-14s %4d records, ops %s" % (key, len(seq), op_hist(seq)))
    modes = mod.modes()
    p("  modes: %d (resolutionData %d bytes each)" % (len(modes), RES_SIZE))
    for m in modes:
        p("   mode %d: %dx%d @ %.2f fps, %d bit, %s x%d, pixel clock %d Hz, lane rate %d kbit/s, "
          "cfa code %d, data type 0x%02x, %d records, ops %s"
          % (m["index"], m["width"], m["height"], m["fps"], m["bits"],
             "C-PHY trios" if m["cphy"] else "D-PHY lanes", m["lanes"], m["pixel_clock"],
             lane_rate_kbps(m), m["cfa"], m["data_type"], len(m["records"]), op_hist(m["records"])))
    used = sum(len(m["records"]) for m in modes)
    fixed = sum(len(mod.sequence(k)) for k in SEQ_ORDER)
    p("  coverage: mode records %d, fixed sequence records %d, other regSetting records %d"
      % (used, fixed, sum(s["dsz"] // REG_SIZE for s in arrays) - used - fixed))


def pack_record(r):
    flags = 1 if r["slave"] is not None else 0
    return struct.pack("<IIIBBBBHH", r["addr"], r["data"], r["delay_us"], r["op"],
                       ADDR_BYTES.get(r["addr_type"], 0), ADDR_BYTES.get(r["data_type"], 0),
                       flags, (r["slave"] or 0) & 0xFFFF, 0)


def build_record_file(mod, sensor_index, name, bayer):
    modes = mod.modes()
    seqs = [mod.sequence(k) for k in SEQ_ORDER]
    n = len(modes)
    off = 48 + 8 * len(SEQ_ORDER) + 56 * n
    body_ops = []
    seq_tab = b""
    for s in seqs:
        seq_tab += struct.pack("<II", off if s else 0, len(s))
        body_ops.append(b"".join(pack_record(r) for r in s))
        off += 20 * len(s)
    mode_tab = b""
    for m in modes:
        mbus = 0
        if m["cfa"] == 4 and m["bits"] == 10:
            mbus = Y10
        elif bayer and m["bits"] == 10 and name != "vd55g0":
            mbus = BAYER[bayer]
        mode_tab += struct.pack(
            "<HHIBBBBBBHIIIIIIIIII", m["width"], m["height"], int(round(m["fps"] * 1000)),
            m["lanes"], m["cphy"], m["bits"], m["data_type"], 0, m["cfa"], 0, m["pixel_clock"],
            lane_rate_kbps(m), m["line_length"], m["frame_length"], m["min_vblank"],
            m["min_hblank"], mbus, off if m["records"] else 0, len(m["records"]), 0)
        body_ops.append(b"".join(pack_record(r) for r in m["records"]))
        off += 20 * len(m["records"])
    if len(mode_tab) != 56 * n:
        raise FormatError("internal: mode record size %d" % (len(mode_tab) // max(n, 1)))
    body = seq_tab + mode_tab + b"".join(body_ops)
    total = 48 + len(body)
    cfa = modes[0]["cfa"] if modes else 0
    nm = name.encode()[:16].ljust(16, b"\0")
    hdr = struct.pack("<8sHHIIHHII16s", b"SPMODREC", 1, 48, total, 0, n, sensor_index, cfa, 0, nm)
    crc = zlib.crc32(body) & 0xFFFFFFFF
    hdr = hdr[:16] + struct.pack("<I", crc) + hdr[20:]
    return hdr + body


def check_emit_dir(d):
    real = os.path.realpath(d)
    p = real
    while not os.path.isdir(p):
        p = os.path.dirname(p)
    q = p
    top = None
    while True:
        if os.path.exists(os.path.join(q, ".git")):
            top = q
            break
        nq = os.path.dirname(q)
        if nq == q:
            break
        q = nq
    if top is None:
        return real
    rel = os.path.relpath(real, top)
    probe = os.path.join(rel, "x")
    r = subprocess.run(["git", "-C", top, "check-ignore", "-q", "--no-index", probe],
                       capture_output=True)
    if r.returncode == 0:
        return real
    raise SystemExit("refusing: %s is inside the git tree %s and not ignored by git" % (real, top))


def find(winroot, sensor):
    pkg, fn, _, _ = SENSORS[sensor]
    hits = glob.glob(os.path.join(winroot, "DriverStore", pkg, fn))
    if len(hits) != 1:
        raise SystemExit("cannot find %s under %s (%d hits)" % (fn, winroot, len(hits)))
    return hits[0]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sensors", nargs="*", help="rear, front, ir (default: all)")
    ap.add_argument("--file", action="append", default=[], help="a module file instead of the DriverStore")
    ap.add_argument("--windows-dir", default=os.path.join(repo, "sources", "windows"))
    ap.add_argument("--emit", metavar="DIR", help="write SPMODREC v1 files here (outside git or git-ignored)")
    ap.add_argument("--bayer", choices=sorted(BAYER),
                    help="fill mbus_code of colour sensors with this order (Bayer order is Unknown)")
    a = ap.parse_args()
    todo = []
    for s in (a.sensors or ([] if a.file else list(SENSORS))):
        if s not in SENSORS:
            ap.error("unknown sensor %s (rear, front, ir)" % s)
        todo.append((s, find(a.windows_dir, s)))
    for f in a.file:
        todo.append(("file", f))
    outdir = check_emit_dir(a.emit) if a.emit else None
    if outdir:
        os.makedirs(outdir, mode=0o700, exist_ok=True)
    rc = 0
    for label, path in todo:
        try:
            mod = Module(path)
            describe(mod, label)
            if outdir:
                if label not in SENSORS:
                    print("  not emitted: --emit needs a named sensor")
                    continue
                _, _, idx, name = SENSORS[label]
                blob = build_record_file(mod, idx, name, a.bayer)
                dst = os.path.join(outdir, name + ".records.bin")
                with open(dst, "wb") as fh:
                    fh.write(blob)
                os.chmod(dst, 0o600)
                print("  emitted %s (%d bytes)" % (dst, len(blob)))
        except FormatError as e:
            print("== %s: ERROR %s" % (label, e))
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
