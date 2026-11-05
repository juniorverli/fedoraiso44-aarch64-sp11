#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# Assisted-by: Claude Sonnet 5.5
"""Derive libcamera Software ISP tuning files from the Windows Qualcomm CamX tuning data.

The Windows image quality of the Surface Pro 11 cameras lives in the CamX tuned
binaries (com.surface.tuned.<module>.bin, QTI Chromatix container, parser V3.4.0).
libcamera 0.7.2 has no access to the Qualcomm ISP, but its simple pipeline Software
ISP reads a small YAML tuning file. This tool replays what that file can express:

  Windows block (module, location)              libcamera tuning element
  -------------------------------------------   -----------------------------------
  demuxblklevel14_ife_v2 (4 channel black,      BlackLevel: blackLevel (16 bit scale,
    14 bit scale, mean of the channels)           single value for all channels)
  cc13_ipe_v2 (3x3 matrix per CCT band, rows    Ccm: ccms [{ct, ccm}] (one entry per
    sum to 1; lowest lux-index bin)               CCT band, ct = band centre)
  gamma15_ipe_v2 (257 entry float LUT, 10 bit)  Adjust: gamma (power law fitted to the
                                                  LUT; read only by libcamera-sp11.patch,
                                                  ignored by stock 0.7.2)
  MWBGainV1 (gain triplets per illuminant)      Awb: maxGains [red, green, blue] (the
                                                  estimator ceiling; stock 4.0 clips the
                                                  calibrated red/blue range)

Dropped (the Software ISP cannot do it, see the evidence file): lens shading
(lsc41), AWB reference points beyond the gain ceiling, ABF/ANR/TF/HNR denoise, ASF sharpening, GTM/LTM tone
mapping, HDR, GIC, PDPC/BPC, chromatic aberration, per-lux CCM selection, the Windows
AEC. The lens shading mesh is written to a separate private sidecar so a future
libcamera LSC stage can use it.

Output is PRIVATE (risk S5): the YAML carries values derived from Windows data. The
tool refuses an output directory inside the git work tree unless git ignores it (the
repository's /out). Never commit, never put in the public ISO; the private image mode
installs the files under /usr/share/libcamera/ipa/simple/<sensor>.yaml.

    python3 -I build-libcamera-tuning.py --inventory          # structure only
    python3 -I build-libcamera-tuning.py                      # emit ov13858 + imx681
    python3 -I build-libcamera-tuning.py --validate           # emit, then libcamera parser
    python3 -I build-libcamera-tuning.py --check-only         # decode and report, no files

Everything printed is structure, counts or pass/fail: never a tuning value.
"""

import argparse
import glob
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import zlib

MAGIC = b"QTI Chromatix Header"
SYM_SIZE = 0x38
CCT_LIMITS = (1000.0, 12000.0)  # control variable whose breakpoints fall here is a CCT

SENSORS = {
    "ov13858": dict(
        glob="surfacecamrearsensor_extension8380.inf_arm64_*/com.surface.tuned.rfc_ov13858.bin",
        bayer="bggr",
        emit=True,
        note="rear, MSHW0491",
    ),
    "imx681": dict(
        glob="surfacecamfrontsensor_extension8380.inf_arm64_*/com.surface.tuned.ffc_imx681.bin",
        bayer="rggb",
        emit=True,
        note="front, MSHW0490",
    ),
    "vd55g0": dict(
        glob="surfacecamauxsensor_extension8380.inf_arm64_*/com.surface.tuned.aux_vd55g0_MSHW0492.bin",
        bayer="mono",
        emit=False,  # monochrome: the Software ISP debayer has no luma-only input
        note="IR, MSHW0492",
    ),
}


class FormatError(Exception):
    pass


# --------------------------------------------------------------------------- container


class Chromatix:
    """Tolerant reader of a QTI Chromatix container (structure level)."""

    def __init__(self, path):
        self.path = path
        b = self.b = open(path, "rb").read()
        self.sha256 = hashlib.sha256(b).hexdigest()
        if b[: len(MAGIC)] != MAGIC or len(b) < 0xD0:
            raise FormatError("not a QTI Chromatix file")
        if struct.unpack_from("<I", b, 0x1C)[0] != len(b) - 4:
            raise FormatError("size field mismatch")
        self.crc_ok = zlib.crc32(b[:-4]) & 0xFFFFFFFF == struct.unpack_from("<I", b, len(b) - 4)[0]
        if not self.crc_ok:
            raise FormatError("CRC-32 trailer mismatch")
        self.name = b[0x58:0x98].split(b"\0")[0].decode("latin1")
        to, n = struct.unpack_from("<II", b, 0xA0)
        self.secs = [struct.unpack_from("<III", b, to + 12 * i) for i in range(n)]
        sec = {s[0]: s for s in self.secs}
        if 0 not in sec or 1 not in sec:
            raise FormatError("symbol or data section missing")
        _, so, ss = sec[0]
        _, do, ds = sec[1]
        self.syms = []
        self.by = {}
        for i in range(ss // SYM_SIZE):
            o = so + i * SYM_SIZE
            idx = struct.unpack_from("<I", b, o)[0]
            name = b[o + 4:o + 36].split(b"\0")[0].decode("latin1")
            doff, dsz = struct.unpack_from("<II", b, o + 48)
            if doff + dsz > ds:
                raise FormatError("symbol %d data outside the data section" % idx)
            s = dict(idx=idx, name=name, foff=do + doff, dsz=dsz)
            if idx in self.by:
                raise FormatError("duplicate symbol index")
            self.syms.append(s)
            self.by[idx] = s

    def data(self, idx):
        s = self.by[idx]
        return self.b[s["foff"]:s["foff"] + s["dsz"]]

    def words(self, idx):
        d = self.data(idx)
        return struct.unpack_from("<%dI" % (len(d) // 4), d, 0)

    def floats(self, idx):
        d = self.data(idx)
        return list(struct.unpack_from("<%df" % (len(d) // 4), d, 0))


ROOT_SUFFIXES = ("_ife_v2", "_bps_v2", "_ipe_v2", "_sfe_v2", "_ife_lite_v2", "_sw_v2",
                 "_aon_v2", "_ife", "_ipe", "_bps", "_sw")


def module_roots(m):
    """Symbols that are processing module roots (name pattern, size of a root object)."""
    return [s for s in m.syms if s["dsz"] >= 40 and s["name"].endswith(ROOT_SUFFIXES)]


def root_refs(m, root):
    """(count, symbol) pairs of the root object that name a symbol (structure)."""
    w = m.words(root["idx"])
    out = []
    for i in range(len(w) - 1):
        if w[i] >= 1 and w[i + 1] in m.by:
            out.append((w[i], w[i + 1]))
    return out


def trigger_root(m, root):
    for c, r in root_refs(m, root):
        n = m.by[r]["name"]
        if n.startswith("mod_") and n.endswith("_trigger_data"):
            return r
    return None


def control_types(m, root):
    for c, r in root_refs(m, root):
        if m.by[r]["name"] == "control_var_type":
            return list(m.words(r))
    return []


def trigger_leaves(m, tdata_idx):
    """Walk the trigger tree: node = {f32 lo, f32 hi, u32 n_children, u32 children, u32 n_regions,
    u32 regions}. Returns [(path[(lo,hi)...], region_count, region_symbol)] of the nodes that
    carry region data. A path has one range per control variable of the module."""
    out = []

    def rec(path, node):
        lo, hi, tc, tr, rc, rr = node
        p = path + [(lo, hi)]
        if rc > 0:
            out.append((p, rc, rr))
        if tc > 0:
            d = m.data(tr)
            if len(d) < 24 * tc:
                raise FormatError("trigger children outside their symbol")
            for i in range(tc):
                rec(p, struct.unpack_from("<ffIIII", d, 24 * i))

    d = m.data(tdata_idx)
    if len(d) < 24:
        return out
    rec([], struct.unpack_from("<ffIIII", d, 0))
    return out


def variants(m, name):
    """All roots of one module name, each with its control list and leaves."""
    res = []
    for r in module_roots(m):
        if r["name"] != name:
            continue
        t = trigger_root(m, r)
        res.append(dict(root=r, ctrl=control_types(m, r),
                        leaves=trigger_leaves(m, t) if t else []))
    return res


# --------------------------------------------------------------------------- inventory


def inventory(m, label):
    names = {}
    for s in m.syms:
        names.setdefault(s["name"], 0)
        names[s["name"]] += 1
    print("== %s: %d bytes, sha256 %s, CRC ok, %d symbols, %d distinct names"
          % (label, len(m.b), m.sha256[:16], len(m.syms), len(names)))
    print("   sections (id,size): %s" % [(s[0], s[2]) for s in m.secs])
    groups = {}
    for r in module_roots(m):
        groups.setdefault(r["name"], []).append(r)
    print("   processing modules: %d distinct, %d roots" % (len(groups), sum(map(len, groups.values()))))
    for name in sorted(groups):
        vs = variants(m, name)
        leaves = [len(v["leaves"]) for v in vs]
        sizes = sorted({m.by[rr]["dsz"] // max(rc, 1) for v in vs for _, rc, rr in v["leaves"]})
        ctrl = [v["ctrl"] for v in vs][0] if vs else []
        print("   %-26s variants=%-2d leaves=%-14s region_bytes=%-12s ctrl=%s"
              % (name, len(vs), ",".join(map(str, leaves[:8])) + ("..." if len(leaves) > 8 else ""),
                 sizes[:3], ctrl))
    stats = [n for n in names if n.startswith("aecx") or n in (
        "refPtV1", "referenceCCTs", "custRefPtV1", "flashRefPtV1", "MWBGainV1",
        "temporalAWBV1", "sensorCalV1", "AWBExtensionParam", "AONAEC", "ASDTuningData",
        "AFDTuningData", "bestShotV1", "ledTorchV1", "faceAssistV1")]
    print("   3A blocks present (names only): %d aecx*, AWB: %s"
          % (sum(1 for n in stats if n.startswith("aecx")),
             sorted(n for n in stats if not n.startswith("aecx"))))


# --------------------------------------------------------------------------- decoding


def identity9(f):
    return all(abs(f[i] - (1.0 if i in (0, 4, 8) else 0.0)) < 1e-6 for i in range(9))


def pick_black(m, notes):
    """Mean of the four demux black levels (14 bit scale), median over variants."""
    vs = variants(m, "demuxblklevel14_ife_v2")
    if not vs or not vs[0]["leaves"]:
        raise FormatError("no demuxblklevel14_ife_v2 black level block")
    means = []
    spread = 0.0
    for v in vs:
        for _, rc, rr in v["leaves"]:
            f = m.floats(rr)[:4]
            if len(f) != 4 or not all(math.isfinite(x) and 0 <= x < 16384 for x in f):
                raise FormatError("black level block is not 4 plausible floats")
            mean = sum(f) / 4.0
            means.append(mean)
            spread = max(spread, (max(f) - min(f)) / mean if mean else 0.0)
    means.sort()
    mean14 = means[len(means) // 2]
    notes.append("black level: %d leaves in %d variants, channel spread <= 10%%: %s, variants equal: %s"
                 % (len(means), len(vs), spread <= 0.10, max(means) - min(means) < 0.05 * mean14))
    # 14 bit -> 16 bit libcamera scale
    return int(round(mean14 * 4.0))


def pick_ccms(m, notes):
    """cc13_ipe_v2: choose the first variant that is not identity; keep the lowest lux-index
    bin; one entry per CCT band (ct = centre of the band)."""
    vs = variants(m, "cc13_ipe_v2")
    usable = []
    for v in vs:
        mats = [m.floats(rr)[:9] for _, _, rr in v["leaves"]]
        if mats and not all(identity9(f) for f in mats):
            usable.append(v)
    if not usable:
        raise FormatError("no non-identity cc13_ipe_v2 variant")
    v = usable[0]
    depth = len(v["leaves"][0][0])
    distinct = []
    for d in range(depth):
        pts = sorted({x for p, _, _ in v["leaves"] for x in p[d]})
        distinct.append(pts)
    # a CCT control has several breakpoints, almost all in the kelvin range; the first band may
    # start at a sentinel below the range
    def in_k(x):
        return CCT_LIMITS[0] <= x <= CCT_LIMITS[1]
    cct = [d for d in range(depth) if len(distinct[d]) > 2
           and sum(map(in_k, distinct[d])) >= len(distinct[d]) - 1
           and not any(x > CCT_LIMITS[1] for x in distinct[d])]
    if len(cct) != 1:
        raise FormatError("cannot identify the CCT control variable (%d candidates)" % len(cct))
    cct = cct[0]
    other = [d for d in range(depth) if d != cct and len(distinct[d]) > 2]
    leaves = v["leaves"]
    if other:
        lux = other[0]
        lo = min(p[lux][0] for p, _, _ in leaves)
        leaves = [x for x in leaves if x[0][lux][0] == lo]
    entries = {}
    row_ok = True
    off_zero = True
    for p, rc, rr in leaves:
        w = m.words(rr)
        f = m.floats(rr)[:9]
        if not all(math.isfinite(x) and abs(x) < 8 for x in f):
            raise FormatError("CCM is not 9 plausible floats")
        for r in range(3):
            if abs(sum(f[3 * r:3 * r + 3]) - 1.0) > 0.03:
                row_ok = False
        if any(w[9:12]):
            off_zero = False
        lo, hi = p[cct]
        if not in_k(lo):
            ct = hi  # open lower band: use its upper edge, libcamera clamps below the first entry
        elif not in_k(hi):
            ct = lo
        else:
            ct = (lo + hi) / 2.0
        entries[int(round(ct))] = f
    notes.append("ccm: %d non-identity variants of %d, %d leaves, kept %d CCT bands (lowest lux-index bin), "
                 "rows sum to 1: %s, offsets zero: %s"
                 % (len(usable), len(vs), len(v["leaves"]), len(entries), row_ok, off_zero))
    return sorted(entries.items())


def pick_gamma(m, notes):
    """Fit y = x**g to the first gamma15_ipe_v2 LUT (257 floats per channel, 3 channels)."""
    vs = variants(m, "gamma15_ipe_v2")
    if not vs or not vs[0]["leaves"]:
        return None
    rr = vs[0]["leaves"][0][2]
    f = m.floats(rr)
    if len(f) < 257:
        return None
    lut = f[:257]
    mx = max(lut)
    if not (mx > 0 and all(math.isfinite(x) for x in lut)):
        return None
    y = [v / mx for v in lut]
    num = den = 0.0
    for i in range(10, 247):
        if y[i] <= 0:
            return None
        lx = math.log(i / 256.0)
        num += math.log(y[i]) * lx
        den += lx * lx
    e = num / den  # y = x**e, libcamera gamma = 1/e
    rms = math.sqrt(sum((y[i] - (i / 256.0) ** e) ** 2 for i in range(10, 247)) / 237.0)
    notes.append("gamma: %d lux bins of LUT, power-law fit rms < 0.05: %s (the LUT also carries tone shaping)"
                 % (len(vs[0]["leaves"]), rms < 0.05))
    if not 0.3 < e < 0.7:
        return None
    return round(1.0 / e, 3)


def lsc_sidecar(m, notes):
    """Lens shading meshes of the lsc41 IFE module: 4 channels x 221 floats + 8 words per leaf."""
    vs = variants(m, "lsc41_ife_v2")
    if not vs:
        return None
    v = vs[0]
    out = []
    for p, rc, rr in v["leaves"]:
        w = m.words(rr)
        if len(w) != 892:
            notes.append("lsc: unexpected region size %d words, no sidecar" % len(w))
            return None
        out.append(dict(ranges=[[round(a, 3), round(b, 3)] for a, b in p],
                        mesh=m.floats(rr)[:884], tail=list(w[884:])))
    notes.append("lsc: %d meshes of 4 x 221 floats (13x17 assumed, order Unknown) written to the private sidecar, "
                 "not consumed by libcamera 0.7.2" % len(out))
    return dict(ctrl=v["ctrl"], leaves=out)


# --------------------------------------------------------------------------- output


def check_out_dir(d):
    d = os.path.realpath(d)
    try:
        top = subprocess.run(["git", "-C", os.path.dirname(d) if os.path.isdir(os.path.dirname(d)) else ".",
                              "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return d
    if top.returncode != 0:
        return d  # not inside a git work tree
    os.makedirs(d, exist_ok=True)
    ign = subprocess.run(["git", "-C", d, "check-ignore", "-q", d])
    if ign.returncode != 0:
        sys.exit("refusing %s: inside a git work tree and not ignored (risk S5)" % d)
    return d


def pick_awb_limits(m, notes):
    """Derived AWB estimator ceiling from the module's calibrated gain ladder.

    MWBGainV1 carries (red, green, blue) gain triplets with green normalised
    to 1, one per illuminant. The Software ISP's stock red/blue ceiling of
    4.0 is below what the front module's own calibration needs, so the
    estimator saturates and leaves a colour cast. The YAML states the larger
    of 4.0 and the vendor maximum with a 10% margin, capped at 16.
    """
    vs = [s for s in m.syms if s["name"] == "MWBGainV1"]
    if not vs:
        notes.append("awb: no MWBGainV1 block; keeping the stock 4.0/4.0 gain limits")
        return None
    trip = []
    for s in vs:
        body = m.floats(s["idx"])[6:]
        if len(body) < 12 or len(body) % 3:
            continue
        for i in range(0, len(body), 3):
            r, g, b = body[i:i + 3]
            if all(math.isfinite(x) for x in (r, g, b)) and 0.05 < g <= 2.0                and 0.05 <= r <= 16.0 and 0.05 <= b <= 16.0:
                trip.append((r, b))
    if len(trip) < 4:
        notes.append("awb: MWBGainV1 yielded too few plausible triplets; keeping stock limits")
        return None
    red = min(16.0, max(4.0, math.ceil(max(r for r, _ in trip) * 1.10 * 100) / 100))
    blue = min(16.0, max(4.0, math.ceil(max(b for _, b in trip) * 1.10 * 100) / 100))
    notes.append("awb: %d calibrated gain triplets, ceiling red %.2f blue %.2f (stock 4.00/4.00)"
                 % (len(trip), red, blue))
    return (red, blue)


def yaml_text(sensor, black, ccms, gamma, src_hash, awb_max=None):
    L = ["# SPDX-License-Identifier: CC0-1.0",
         "# PRIVATE: derived from Windows CamX tuning data of the operator's own device (risk S5).",
         "# Never commit, never publish. Generated by build-libcamera-tuning.py (Assisted-by: Claude Sonnet 5.5).",
         "# Source sha256 %s." % src_hash[:16],
         "%YAML 1.1", "---", "version: 1", "algorithms:",
         "  - BlackLevel:",
         "      blackLevel: %d" % black,
         "  - Awb:"]
    if awb_max:
        L.append("      maxGains: [ %.2f, 1.0, %.2f ]" % awb_max)
    if ccms:
        L.append("  - Ccm:")
        L.append("      ccms:")
        for ct, f in ccms:
            L.append("        - ct: %d" % ct)
            L.append("          ccm: [ %s ]" % ", ".join("%.6f" % x for x in f))
    if gamma:
        L.append("  - Adjust:")
        L.append("      gamma: %.3f" % gamma)
    else:
        L.append("  - Adjust:")
    L.append("  - Agc:")
    L.append("...")
    return "\n".join(L) + "\n"


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--windows-dir", default=os.path.join(repo, "sources", "windows"))
    ap.add_argument("--out-dir", default=os.path.join(repo, "out", "firmware-private", "cameras", "libcamera"))
    ap.add_argument("--sensors", nargs="*", default=["ov13858", "imx681"])
    ap.add_argument("--inventory", action="store_true", help="print structure of the tuned files and exit")
    ap.add_argument("--check-only", action="store_true", help="decode and report, write nothing")
    ap.add_argument("--validate", action="store_true", help="run validate-tuning.sh on the emitted files")
    ap.add_argument("--no-lsc-sidecar", action="store_true")
    a = ap.parse_args()

    store = os.path.join(a.windows_dir, "DriverStore")
    targets = list(SENSORS) if a.inventory else a.sensors
    emitted = []
    manifest = {}
    rc = 0
    for name in targets:
        cfg = SENSORS[name]
        hits = sorted(glob.glob(os.path.join(store, cfg["glob"])))
        if not hits:
            print("%s: tuned file not found under %s" % (name, store), file=sys.stderr)
            rc = 1
            continue
        m = Chromatix(hits[0])
        if a.inventory:
            inventory(m, "%s (%s)" % (name, cfg["note"]))
            continue
        if not cfg["emit"]:
            print("%s: skipped (monochrome, no Software ISP input)" % name)
            continue
        notes = []
        try:
            black = pick_black(m, notes)
            ccms = pick_ccms(m, notes)
            gamma = pick_gamma(m, notes)
            awb_max = pick_awb_limits(m, notes)
            lsc = None if a.no_lsc_sidecar else lsc_sidecar(m, notes)
        except FormatError as e:
            print("%s: FAIL %s" % (name, e), file=sys.stderr)
            rc = 1
            continue
        print("%s: source %s (%d bytes)" % (name, os.path.basename(hits[0]), len(m.b)))
        for n in notes:
            print("   " + n)
        text = yaml_text(name, black, ccms, gamma, m.sha256, awb_max)
        manifest[name] = dict(source=os.path.basename(hits[0]), source_sha256=m.sha256,
                              yaml_sha256=hashlib.sha256(text.encode()).hexdigest(),
                              ccm_entries=len(ccms), gamma_key=bool(gamma),
                              awb_max_gains=list(awb_max) if awb_max else None,
                              lsc_meshes=len(lsc["leaves"]) if lsc else 0)
        if a.check_only:
            continue
        out = check_out_dir(a.out_dir)
        os.makedirs(out, exist_ok=True)
        path = os.path.join(out, name + ".yaml")
        with open(path, "w") as fh:
            fh.write(text)
        os.chmod(path, 0o600)
        emitted.append(path)
        print("   wrote %s (%d bytes, mode 600)" % (path, len(text)))
        if lsc:
            sp = os.path.join(out, name + ".lsc-mesh.private.json")
            with open(sp, "w") as fh:
                json.dump(lsc, fh)
            os.chmod(sp, 0o600)
            print("   wrote %s" % sp)
    if emitted:
        mp = os.path.join(os.path.dirname(emitted[0]), "libcamera-tuning.manifest.json")
        with open(mp, "w") as fh:
            json.dump(manifest, fh, indent=1)
        print("manifest %s (hashes only)" % mp)
    if a.validate and emitted:
        rc |= subprocess.call([os.path.join(here, "validate-tuning.sh")] + emitted)
    return rc


if __name__ == "__main__":
    sys.exit(main())
