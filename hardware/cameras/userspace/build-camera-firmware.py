#!/usr/bin/env python3
"""Build the local camera register blobs for the Surface Pro 11 (SRB v2).

The kernel drivers imx681 and ov13858 take their sensor register sequences from
a firmware file (the "register blob", format in drivers/media/i2c/sensor-regblob.h
of the kernel series, patch 0011). Those sequences are Windows vendor data and
must never enter git (risk S5). This tool reads the data the operator already
has on this machine (sources/windows) and writes the blobs under
out/firmware-private/cameras/, from where the private image mode (D25) installs
them in /usr/lib/firmware. Nothing this tool writes may be committed, shared or
published. The manifest it writes holds hashes and counts, never register values.

    python3 -I hardware/cameras/userspace/build-camera-firmware.py all
    python3 -I hardware/cameras/userspace/build-camera-firmware.py all \\
        --bayer-imx681 bggr          # IMX681 order Unknown: default rggb, see below
    python3 -I hardware/cameras/userspace/build-camera-firmware.py ov13858
    python3 -I hardware/cameras/userspace/build-camera-firmware.py imx681 --bayer rggb
    python3 -I hardware/cameras/userspace/build-camera-firmware.py vd55g0      # design only

Outputs (default --out out/firmware-private/cameras):
    ov13858-mshw0491.bin    rear; modes only (the driver uses nothing else)
    imx681-mshw0490.bin     front; init, stream on/off, controls, modes
    vd55g0-mshw0492.bin     IR (module file MSHW0492, never MSHW0472); same layout,
                            no driver exists yet (design only)
    MANIFEST.json           input and output SHA-256, counts, no register values

What is read (Chromatix "sensor module" data and AeoB "SCFG" data):

  * Chromatix container: header 'QTI Chromatix Header', section table at 0xA0,
    symbol table of 0x38-byte records, data section. regSetting arrays: 40-byte
    elements. Layout verified against the sensor modules by the earlier survey
    (rea/camera/tools in the surface repository, outside this repository) with
    2151 rows and 0 mismatches.
  * Roles of the regSetting arrays (Verified on all three modules by content:
    stream on writes 0x0100=1 for OV13858 and IMX681):
      - init: the 'initSetting' symbol holds (count, regSetting symbol);
      - stream on, stream off, group-hold on, group-hold off: the four
        (count, symbol) pairs inside 'sensorDriverData', in this order;
      - per mode: the 'resSettings' symbols.
  * Per mode geometry: 'resolutionData' records of 252 bytes (line length at
    +0x24, frame length +0x28, minimum vertical blanking +0x30, output pixel
    clock +0x34, lane or trio count +0x50, C-PHY flag +0x60). Each record owns
    its arrays through pointers (Verified by hardware/cameras/evidence/
    2026-10-30-module-data-format.md): (count 1, symbol) of its
    'streamConfiguration' at +0x14/+0x18 (width, height, bit width) and of its
    'resSettings' at +0x6C/+0x70. The tool follows these pointers; it does not
    pair arrays by symbol order any more.
  * SCFG_*.bin (AeoB): the sensor module file name, and the identification
    register and expected value (second integer: high 16 bits value, low 16 bits
    register).

What is Inference or Unknown here (REA, after the audio agent releases it, or a
RAW capture on the device, settles each; the evidence files in
hardware/cameras/evidence/ carry the same list):

  1. (Resolved) Mode i owns its streamConfiguration and resSettings through the
     pointers in its resolutionData record. The tool asserts the symbols have
     the expected names and sizes, and reports in the manifest whether the
     pointers agree with the older "same order" guess.
  2. Colour filter: the module carries a numeric CamX code (3 for IMX681, 0 for
     OV13858, 4 for the mono IR) with no printable enumeration.
       - OV13858: GRBG (Inference, medium: the Windows windows start on even
         columns and rows and keep the flip bits of the Linux full mode, which
         is GRBG). The tool emits GRBG and accepts no other order.
       - IMX681: Unknown. --bayer-imx681 / --bayer default to rggb and the tool
         prints a loud note: the order is a guess and one RAW capture of a
         coloured target decides (swapped red and blue means bggr).
  3. Control registers of the IMX681: the module names the digital gain
     (0x020e), the short exposure (0x0224) and a non-standard middle exposure
     (0x30b2) only; the analogue gain register and the gain code law are not in
     the module (realToRegGain is empty). With --ccs-controls the tool uses the
     public MIPI CCS addresses (exposure 0x0202, analogue gain 0x0204, frame
     length 0x0340, 16 bit big endian), which is an Inference from the IMX681
     init writing CCS registers (0x0111, 0x0112, 0x0114, 0x0136). The gain code
     range must be given (--again-range) and the law between code and gain is
     Unknown (libcamera needs it, see the evidence file).
  4. Line length units: the register value of OV13858 is 1122 and the Linux
     driver's pixels per line for the same register value is 4488 (x4, Verified
     in ov13858.c), so the OV13858 profile scales by 4. For the IMX681 and the
     VD55G0 the scale is not known and is 1; their hblank and frame rate
     figures are Unknown until measured.
  5. Operation 4 of the module (VD55G0 only) is a POLL: read the register until
     it equals the data value, the delay field being the timeout in microseconds
     (Inference, strong: the records sit where vd55g1.c polls the boot command
     and FSM state registers). The tool emits an SRB v2 POLL (expected value,
     mask 0xff because the module has no mask, timeout in microseconds) and
     never "write then sleep". A poll without a timeout, with a 16 bit value or
     with a timeout above the format limit is an error.
  6. IR illuminator (risk S2): the VD55G0 module programs the sensor's GPIO1 as
     a strobe output (register 0x0468 = 2, from the earlier survey's register
     map of the sensor). The VD55G0 profile rewrites that write to 1 (input), so
     the sensor never drives a strobe even if a PMIC flash path were armed.
     That register map is an Inference (it differs from vd55g1.c). The module
     file is the MSHW0492 one (the device's hardware id); the MSHW0472 file
     belongs to another SKU.

Anything the tool does not understand is an error, never a guess.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import struct
import sys
import zlib

MAGIC = b"SPSRBLOB"
HDR = 64
OP_SIZE, CTRL_SIZE, MODE_SIZE = 4, 20, 40
OP_WRITE8, OP_DELAY_MS, OP_POLL = 0, 1, 2
SRB_VERSION = 2
SRB_MAX_POLL_US = 10000000
MOD_POLL = 4          # operation code of a poll record in the Chromatix module
CTRL_EXPOSURE, CTRL_GAIN, CTRL_FRAME_LENGTH = 1, 2, 3
BAYER = {"bggr": 0x3007, "gbrg": 0x300E, "grbg": 0x300A, "rggb": 0x300F}
Y10 = 0x200A

# Per sensor profile. 'dirs' are the DriverStore packages (hash suffix globbed).
PROFILES = {
    "ov13858": dict(
        name="ov13858-mshw0491.bin",
        pkg="surfacecamrearsensor_extension8380.inf_arm64_*",
        module="com.surface.sensormodule.rfc_ov13858.bin",
        scfg="SCFG_REAR_MSHW0491.bin",
        phy="dphy", lanes=4, color=True, hts_scale=4, skip_modes=[], stream_reg=0x0100,
        bayer_choices=["grbg"], bayer_default="grbg",
    ),
    "imx681": dict(
        name="imx681-mshw0490.bin",
        pkg="surfacecamfrontsensor_extension8380.inf_arm64_*",
        module="com.surface.sensormodule.ffc_imx681.bin",
        scfg="SCFG_FRONT_MSHW0490.bin",
        phy="cphy", lanes=1, color=True, hts_scale=1, stream_reg=0x0100,
        skip_modes=[5],  # 504x378 at 3 fps presence mode
        bayer_choices=list(BAYER), bayer_default="rggb",
    ),
    "vd55g0": dict(
        name="vd55g0-mshw0492.bin",
        pkg="surfacecamauxsensor_extension8380.inf_arm64_*",
        module="com.surface.sensormodule.aux_vd55g0_MSHW0492.bin",
        scfg="SCFG_AUX_MSHW0492.bin",
        phy="dphy", lanes=1, color=False, hts_scale=1, skip_modes=[],
        bayer_choices=[],
    ),
}


class Fail(Exception):
    pass


# ----------------------------------------------------------------- Chromatix

def load_chromatix(buf):
    if buf[:20] != b"QTI Chromatix Header":
        raise Fail("not a QTI Chromatix module")
    tbl_off, nsec = struct.unpack_from("<II", buf, 0xA0)
    secs = [struct.unpack_from("<III", buf, tbl_off + 12 * i) for i in range(nsec)]
    if nsec < 2:
        raise Fail("unexpected section count %d" % nsec)
    sym_sec, data_sec = secs[0], secs[1]
    syms = []
    for i in range(sym_sec[2] // 0x38):
        off = sym_sec[1] + i * 0x38
        idx, = struct.unpack_from("<I", buf, off)
        name = buf[off + 4:off + 36].split(b"\0")[0].decode("latin1")
        doff, dsz = struct.unpack_from("<II", buf, off + 48)
        syms.append(dict(idx=idx, name=name, dsz=dsz, foff=data_sec[1] + doff))
    return {s["idx"]: s for s in syms}, syms


def decode_regsetting(buf, by, sym):
    """Rows of one regSetting array (40-byte elements)."""
    if sym["name"] != "regSetting" or sym["dsz"] % 40:
        raise Fail("symbol %d is not a regSetting array" % sym["idx"])
    rows = []
    for i in range(sym["dsz"] // 40):
        f = struct.unpack_from("<10I", buf, sym["foff"] + 40 * i)
        rd = by[f[4]]
        vals = list(struct.unpack_from("<%dI" % (rd["dsz"] // 4), buf, rd["foff"])) \
            if rd["dsz"] >= 4 else []
        vals = vals[:f[3]] if f[3] else vals
        delay = 0
        if f[8]:
            ds = by[f[9]]
            delay = struct.unpack_from("<I", buf, ds["foff"])[0] if ds["dsz"] >= 4 else 0
        rows.append(dict(slave=bool(f[0]), addr=f[2], data=vals, at=f[5], dt=f[6],
                         op=f[7], delay_us=delay))
    return rows


def pair_arrays(buf, by, sym):
    """(count, symbol) pairs of a structure that point at regSetting arrays."""
    d = buf[sym["foff"]:sym["foff"] + sym["dsz"]]
    out = []
    for o in range(0, len(d) - 7, 4):
        c, s = struct.unpack_from("<II", d, o)
        t = by.get(s)
        if t and t["name"] == "regSetting" and t["dsz"] // 40 == c and c:
            out.append(t)
    return out


def to_ops(rows, what, profile):
    """Convert regSetting rows to SRB operations.

    Entries: (OP_WRITE8, reg, value), (OP_DELAY_MS, ms, 0) or
    (OP_POLL, reg, expected, mask, timeout_us).
    """
    ops, rewrites = [], 0
    for n, r in enumerate(rows):
        if r["slave"] or r["op"] not in (0, MOD_POLL):
            raise Fail("%s row %d: operation %d with slave=%s is not a plain write or poll"
                       % (what, n, r["op"], r["slave"]))
        if (r["at"], r["dt"], r["addr"]) == (0, 0, 0) and r["data"] in ([0], []):
            continue  # the empty placeholder of the VD55G0 init
        if r["at"] != 2 or len(r["data"]) != 1:
            raise Fail("%s row %d: address type %d, %d data items" %
                       (what, n, r["at"], len(r["data"])))
        v, a = r["data"][0], r["addr"]
        if a > 0xFFFF:
            raise Fail("%s row %d: address 0x%x" % (what, n, a))
        if r["op"] == MOD_POLL:
            if r["dt"] != 1 or v > 0xFF:
                raise Fail("%s row %d: poll with data type %d value 0x%x" % (what, n, r["dt"], v))
            if not 0 < r["delay_us"] <= SRB_MAX_POLL_US:
                raise Fail("%s row %d: poll timeout %d us" % (what, n, r["delay_us"]))
            ops.append((OP_POLL, a, v, 0xFF, r["delay_us"]))
            continue
        if r["dt"] == 1 and v <= 0xFF:
            writes = [(a, v)]
        elif r["dt"] == 2 and v <= 0xFFFF:
            writes = [(a, v >> 8), (a + 1, v & 0xFF)]  # big endian on the wire
        else:
            raise Fail("%s row %d: data type %d value 0x%x" % (what, n, r["dt"], v))
        for reg, val in writes:
            if profile.get("s2_gpio_reg") == reg and val == profile["s2_gpio_from"]:
                val, rewrites = profile["s2_gpio_to"], rewrites + 1
            ops.append((OP_WRITE8, reg, val))
        if r["delay_us"]:
            ms = -(-r["delay_us"] // 1000)
            if ms > 1000:
                raise Fail("%s row %d: delay %d ms" % (what, n, ms))
            ops.append((OP_DELAY_MS, ms, 0))
    return ops, rewrites


# ---------------------------------------------------------------------- AeoB

def read_scfg(buf):
    """Return (module file name, probe register, expected value) of an SCFG file."""
    if buf[:4] != b"AeoB" or struct.unpack_from("<I", buf, 4)[0] != len(buf):
        raise Fail("not an AeoB file or wrong length")
    strs, ints = [], []

    def walk(off, end):
        while off < end:
            t, ln = struct.unpack_from("<HH", buf, off)
            p = off + 4
            if p + ln > end:
                raise Fail("AeoB element overruns its package")
            if t == 3:
                walk(p, p + ln)
            elif t == 1:
                strs.append(buf[p:p + ln].rstrip(b"\0").decode("latin1"))
            elif t == 0:
                ints.append(int.from_bytes(buf[p:p + ln], "little"))
            off = p + max(ln, 4) if t not in (0, 1, 3) else p + ln
    walk(12, len(buf))
    if len(strs) < 1 or len(ints) < 2:
        raise Fail("SCFG has %d strings and %d integers" % (len(strs), len(ints)))
    probe = ints[1]
    return strs[0], probe & 0xFFFF, (probe >> 16) & 0xFFFF


# ---------------------------------------------------------------------- blob

def build_blob(init, on, off, ctrls, modes, ident):
    """init/on/off: op lists. ctrls: dicts. modes: dicts with 'ops'."""
    payload = bytearray()

    def put_ops(ops):
        if not ops:
            return 0, 0
        o = HDR + len(payload)
        slots = 0
        for op in ops:
            kind, a, v = op[:3]
            payload.extend(struct.pack("<HBB", a, v, kind))
            slots += 1
            if kind == OP_POLL:
                mask, timeout = op[3], op[4]
                payload.extend(struct.pack("<B", mask) + struct.pack("<I", timeout)[:3])
                slots += 1
        return o, slots

    init_o = put_ops(init)
    on_o = put_ops(on)
    off_o = put_ops(off)
    for m in modes:
        m["ops_off"], m["ops_count"] = put_ops(m["ops"])
    ctrl_off = 0
    if ctrls:
        ctrl_off = HDR + len(payload)
        for c in ctrls:
            payload.extend(struct.pack("<BBBBHHIII", c["kind"], c["width"], c["flags"], 0,
                                       c["reg"], c["step"], c["min"], c["max"], c["def"]))
    mode_off = 0
    if modes:
        mode_off = HDR + len(payload)
        for m in modes:
            payload.extend(struct.pack(
                "<HHIIIHHHHIIBBHI", m["width"], m["height"], m["code"], m["link_freq"],
                m["pixel_rate"], m["hts"], m["vts"], m["vts_min"], 0, m["ops_off"],
                m["ops_count"], m["lanes"], 0, 0, 0))
    total = HDR + len(payload)
    hdr = bytearray(HDR)
    hdr[0:8] = MAGIC
    struct.pack_into("<HHII", hdr, 8, SRB_VERSION, HDR, total, zlib.crc32(bytes(payload)))
    struct.pack_into("<HH", hdr, 20, len(modes), len(ctrls))
    struct.pack_into("<IIIIII", hdr, 24, init_o[0], init_o[1], on_o[0], on_o[1],
                     off_o[0], off_o[1])
    struct.pack_into("<II", hdr, 48, ctrl_off, mode_off)
    reg, width, flags, value = ident
    struct.pack_into("<HBBI", hdr, 56, reg, width, flags, value)
    return bytes(hdr) + bytes(payload)


def verify_blob(blob):
    """Independent re-parse with the checks of srb_parse(); returns a summary."""
    def u16(o): return struct.unpack_from("<H", blob, o)[0]
    def u32(o): return struct.unpack_from("<I", blob, o)[0]
    assert blob[:8] == MAGIC and u16(8) == SRB_VERSION and u16(10) == HDR
    total = u32(12)
    assert HDR <= total <= len(blob)
    assert zlib.crc32(blob[HDR:total]) == u32(16), "CRC"

    def ops(off, cnt):
        """Check one list of 'cnt' slots; returns (slots, polls)."""
        if not cnt:
            return 0, 0
        assert off >= HDR and off % 4 == 0 and off + cnt * OP_SIZE <= total
        polls, i = 0, 0
        while i < cnt:
            kind = blob[off + 4 * i + 3]
            assert kind in (OP_WRITE8, OP_DELAY_MS, OP_POLL)
            if kind == OP_DELAY_MS:
                assert u16(off + 4 * i) <= 1000
            if kind == OP_POLL:
                assert i + 1 < cnt
                mask = blob[off + 4 * i + 4]
                timeout = int.from_bytes(blob[off + 4 * i + 5:off + 4 * i + 8], "little")
                assert mask and 0 < timeout <= SRB_MAX_POLL_US
                polls += 1
                i += 1
            i += 1
        return cnt, polls
    summary = dict(version=SRB_VERSION, controls=u16(22), modes=[])
    total_polls = 0
    for name, o, c in (("init", 24, 28), ("on", 32, 36), ("off", 40, 44)):
        n, p = ops(u32(o), u32(c))
        summary[name + "_slots"], summary[name + "_polls"] = n, p
        total_polls += p
    nm = u16(20)
    mo = u32(52)
    if nm:
        assert mo >= HDR and mo + nm * MODE_SIZE <= total
    for i in range(nm):
        b = mo + i * MODE_SIZE
        w, h, code, lf, pr, hts, vts, vmin = struct.unpack_from("<HHIIIHHH", blob, b)
        assert w and h and lf and pr and hts >= w and vts >= h and vmin <= vts
        n, p = ops(u32(b + 24), u32(b + 28))
        total_polls += p
        assert 1 <= blob[b + 32] <= 4
        summary["modes"].append(dict(size="%dx%d" % (w, h), code="0x%x" % code,
                                     link_freq_hz=lf, pixel_rate_hz=pr, hts=hts, vts=vts,
                                     lanes=blob[b + 32], op_slots=n, polls=p))
    summary["polls"] = total_polls
    return summary


# ---------------------------------------------------------------------- main

def sha256(path_or_bytes):
    h = hashlib.sha256()
    if isinstance(path_or_bytes, bytes):
        h.update(path_or_bytes)
    else:
        with open(path_or_bytes, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def find_one(root, pkg, name):
    hits = glob.glob(os.path.join(root, "DriverStore", pkg, name))
    if len(hits) != 1:
        raise Fail("expected exactly one %s/%s under %s, found %d" % (pkg, name, root, len(hits)))
    return hits[0]


def build_sensor(key, args):
    prof = dict(PROFILES[key])
    if key == "vd55g0":
        prof.update(s2_gpio_reg=0x0468, s2_gpio_from=2, s2_gpio_to=1)
    mod_path = find_one(args.windows_root, prof["pkg"], prof["module"])
    scfg_path = find_one(args.windows_root, prof["pkg"], prof["scfg"])
    buf = open(mod_path, "rb").read()
    by, syms = load_chromatix(buf)

    scfg_module, id_reg, id_value = read_scfg(open(scfg_path, "rb").read())
    if scfg_module != prof["module"]:
        raise Fail("SCFG names %s, expected %s" % (scfg_module, prof["module"]))

    # roles
    init_sym = [s for s in syms if s["name"] == "initSetting"]
    sdd = [s for s in syms if s["name"] == "sensorDriverData"]
    if len(init_sym) != 1 or len(sdd) != 1:
        raise Fail("initSetting / sensorDriverData not unique")
    ip = pair_arrays(buf, by, init_sym[0])
    sp = pair_arrays(buf, by, sdd[0])
    if len(ip) != 1 or len(sp) != 4:
        raise Fail("found %d init and %d driver arrays, expected 1 and 4" % (len(ip), len(sp)))
    def no_stream_write(ops, what):
        # init and mode sequences must not start the stream: only stream on does
        if prof.get("stream_reg") is not None and \
                any(k == OP_WRITE8 and a == prof["stream_reg"] for k, a, _ in ops):
            raise Fail("%s writes the stream control register 0x%04x" %
                       (what, prof["stream_reg"]))

    init_ops, rw0 = to_ops(decode_regsetting(buf, by, ip[0]), "init", prof)
    no_stream_write(init_ops, "init")
    on_ops, rw1 = to_ops(decode_regsetting(buf, by, sp[0]), "stream on", prof)
    off_ops, rw2 = to_ops(decode_regsetting(buf, by, sp[1]), "stream off", prof)
    if not on_ops or not off_ops:
        raise Fail("empty stream on/off sequence")

    # modes
    res = sorted([s for s in syms if s["name"] == "resSettings"], key=lambda s: s["idx"])
    sc = sorted([s for s in syms if s["name"] == "streamConfiguration"], key=lambda s: s["idx"])
    rdata = [s for s in syms if s["name"] == "resolutionData"]
    if len(rdata) != 1 or rdata[0]["dsz"] % 252:
        raise Fail("resolutionData is not 252-byte records")
    n_modes = rdata[0]["dsz"] // 252
    if not (len(res) == len(sc) == n_modes):
        raise Fail("mode counts differ: %d resSettings, %d streamConfiguration, %d records"
                   % (len(res), len(sc), n_modes))
    notes = []
    code = Y10
    bayer = None
    if prof["color"]:
        bayer = args.bayer or prof["bayer_default"]
        if bayer not in prof["bayer_choices"]:
            raise Fail("%s accepts --bayer %s only" % (key, ",".join(prof["bayer_choices"])))
        code = BAYER[bayer]
        if key == "imx681":
            msg = ("IMX681 Bayer order %s is a GUESS (%s): the module's colour code 3 is "
                   "not decoded. Capture one RAW frame of a coloured target; swapped red "
                   "and blue means rebuild with --bayer-imx681 bggr." %
                   (bayer, "default" if not args.bayer else "from the command line"))
            notes.append(msg)
            print("build-camera-firmware: LOUD NOTE: " + msg, file=sys.stderr)
    pointer_order_ok = True
    modes, rewrites = [], rw0 + rw1 + rw2
    for i in range(n_modes):
        if i in prof["skip_modes"]:
            continue
        rec = rdata[0]["foff"] + 252 * i
        u = lambda o: struct.unpack_from("<I", buf, rec + o)[0]
        # the mode owns its arrays through (count 1, symbol) pointers (Verified)
        if (u(0x14), u(0x6C)) != (1, 1):
            raise Fail("mode %d: pointer counts %d, %d (expected 1, 1)" % (i, u(0x14), u(0x6C)))
        sc_sym, rs_sym = by.get(u(0x18)), by.get(u(0x70))
        if not sc_sym or sc_sym["name"] != "streamConfiguration" or sc_sym["dsz"] != 60:
            raise Fail("mode %d: streamConfiguration pointer" % i)
        if not rs_sym or rs_sym["name"] != "resSettings" or rs_sym["dsz"] != 8:
            raise Fail("mode %d: resSettings pointer" % i)
        pointer_order_ok = pointer_order_ok and sc_sym is sc[i] and rs_sym is res[i]
        scd = struct.unpack_from("<15I", buf, sc_sym["foff"])
        width, height, bw = scd[5], scd[6], scd[7]
        hts, vts, min_vb, pix, lanes, cphy = u(0x24), u(0x28), u(0x30), u(0x34), u(0x50), u(0x60)
        if lanes != prof["lanes"] or bool(cphy) != (prof["phy"] == "cphy"):
            raise Fail("mode %d: lanes %d, C-PHY flag %d do not match the profile" %
                       (i, lanes, cphy))
        # data type 0x2b is RAW10
        if scd[2] != 0x2B or bw != 10:
            raise Fail("mode %d: stream data type 0x%x, %d bit" % (i, scd[2], bw))
        rate = pix * bw / lanes                       # bit/s per lane (D-PHY) or trio
        freq = rate * 7 / 16 / 2 if cphy else rate / 2
        freq = int(round(freq / 1e5)) * 100000        # PLLs are exact multiples
        hts *= prof["hts_scale"]
        vts_min = max(height + min_vb, 0) if min_vb else vts
        mops, rw = to_ops(decode_regsetting(buf, by, by[_array_sym(buf, by, rs_sym)]),
                          "mode %d" % i, prof)
        rewrites += rw
        no_stream_write(mops, "mode %d" % i)
        modes.append(dict(width=width, height=height, code=code, link_freq=freq, pixel_rate=pix, hts=hts, vts=vts,
                          vts_min=min(vts_min, vts), lanes=lanes, ops=mops, index=i))

    # one mode per size (the driver selects a mode by frame size): keep the one with
    # the lowest nominal frame rate, which is the lowest bandwidth
    keep = {}
    for m in modes:
        k = (m["width"], m["height"])
        rate = m["pixel_rate"] / (m["hts"] * m["vts"])
        if k not in keep or rate < keep[k][0]:
            keep[k] = (rate, m)
    keep = {k: v[1] for k, v in keep.items()}
    dropped = [m["index"] for m in modes if keep[(m["width"], m["height"])] is not m]
    modes = [m for m in modes if m["index"] not in dropped]

    ctrls = []
    if args.ccs_controls:
        if key != "imx681":
            raise Fail("--ccs-controls is only for the imx681 profile")
        if not args.again_range:
            raise Fail("--ccs-controls needs --again-range MIN:MAX:STEP:DEFAULT (gain codes)")
        amin, amax, astep, adef = [int(x, 0) for x in args.again_range.split(":")]
        ctrls = [
            dict(kind=CTRL_EXPOSURE, width=2, flags=0, reg=0x0202, step=1, min=4,
                 max=0xFFFF, **{"def": 1000}),
            dict(kind=CTRL_GAIN, width=2, flags=0, reg=0x0204, step=astep, min=amin,
                 max=amax, **{"def": adef}),
            dict(kind=CTRL_FRAME_LENGTH, width=2, flags=0, reg=0x0340, step=1, min=0,
                 max=0xFFFF, **{"def": 0xFFFF}),
        ]
    if key == "vd55g0" and "MSHW0492" not in os.path.basename(mod_path):
        raise Fail("the IR module file must be the MSHW0492 one")
    id_width = 2
    blob = build_blob(init_ops if key != "ov13858" else [], on_ops if key != "ov13858" else [],
                      off_ops if key != "ov13858" else [], ctrls, modes,
                      (id_reg, id_width, 0, id_value))
    summary = verify_blob(blob)
    out = os.path.join(args.out, prof["name"])
    os.makedirs(args.out, exist_ok=True)
    with open(out, "wb") as f:
        f.write(blob)
    os.chmod(out, 0o600)
    return dict(sensor=key, output=out, output_sha256=sha256(blob), bytes=len(blob),
                inputs={os.path.relpath(mod_path, args.windows_root): sha256(mod_path),
                        os.path.relpath(scfg_path, args.windows_root): sha256(scfg_path)},
                dropped_same_size_modes=dropped, skipped_modes=prof["skip_modes"],
                s2_rewrites=rewrites if key == "vd55g0" else 0, bayer=bayer,
                mode_pointers_match_symbol_order=pointer_order_ok, notes=notes,
                summary=summary)


def _array_sym(buf, by, res_sym):
    """The regSetting symbol that a resSettings symbol points at."""
    c, s = struct.unpack_from("<II", buf, res_sym["foff"])
    t = by.get(s)
    if not t or t["name"] != "regSetting" or t["dsz"] // 40 != c:
        raise Fail("resSettings %d does not point at a regSetting array" % res_sym["idx"])
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sensor", choices=["all", "ov13858", "imx681", "vd55g0"])
    ap.add_argument("--windows-root", default="sources/windows")
    ap.add_argument("--out", default="out/firmware-private/cameras")
    ap.add_argument("--bayer", choices=list(BAYER),
                    help="Bayer order of a colour sensor (ov13858: grbg only; imx681: default "
                    "rggb, a GUESS that a RAW capture decides)")
    ap.add_argument("--bayer-imx681", choices=list(BAYER),
                    help="with 'all': order of the IMX681 (default rggb, a GUESS)")
    ap.add_argument("--ccs-controls", action="store_true",
                    help="IMX681: use the public MIPI CCS exposure, gain and frame length registers")
    ap.add_argument("--again-range", help="MIN:MAX:STEP:DEFAULT gain codes for --ccs-controls")
    args = ap.parse_args()
    if "out/firmware-private" not in os.path.normpath(args.out).replace(os.sep, "/") + "/" and \
            not args.out.startswith("/tmp"):
        sys.exit("refusing to write blobs outside out/firmware-private (risk S5)")
    keys = ["ov13858", "imx681"] if args.sensor == "all" else [args.sensor]
    results = []
    for k in keys:
        a = argparse.Namespace(**vars(args))
        if args.sensor == "all":
            a.bayer = {"imx681": args.bayer_imx681}.get(k)
            a.ccs_controls = args.ccs_controls and k == "imx681"
        try:
            results.append(build_sensor(k, a))
        except Fail as e:
            sys.exit("build-camera-firmware: %s: %s" % (k, e))
    manifest = os.path.join(args.out, "MANIFEST.json")
    old = []
    try:
        with open(manifest) as f:
            old = [b for b in json.load(f)["blobs"] if b["sensor"] not in keys]
    except (OSError, ValueError, KeyError):
        pass
    with open(manifest, "w") as f:
        json.dump(dict(tool="hardware/cameras/userspace/build-camera-firmware.py",
                       note="local, never commit or publish (risk S5, decision D25)",
                       blobs=old + results), f, indent=2)
    for r in results:
        print("%s: %d bytes, SRB v%d, sha256 %s, %d modes, %d polls" % (
              r["output"], r["bytes"], r["summary"]["version"], r["output_sha256"][:16],
              len(r["summary"]["modes"]), r["summary"]["polls"]))
    print("manifest:", manifest)


if __name__ == "__main__":
    main()
