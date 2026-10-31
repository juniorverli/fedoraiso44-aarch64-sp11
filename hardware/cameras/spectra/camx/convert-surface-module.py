#!/usr/bin/env python3
"""Map the Surface Windows camera sensor modules onto the Qualcomm Linux CamX sensor-module schema.

Status (2026-10-31): PARTIAL. See hardware/cameras/evidence/2026-10-31-camx-userspace.md.

The Windows files (com.surface.sensormodule.*.bin) are QTI Chromatix containers written by
"Parameter Parser V3.4.0" (container words 3/1, 3 sections, name-keyed symbol table, zlib CRC-32).
The Qualcomm Linux CamX 1.0.56 package ships "Parameter Parser V7.4.1" containers (words 7/0,
5 sections, hashed type definitions with the XSD embedded, 8-byte trailer checksum). The data model
is the same CamX SensorDriverData, the byte format is not. This tool does what is possible without
the Qualcomm parser source:

  --report   (default) structure-only comparison of one Windows module against the Linux
             package modules: container header, sections, field coverage against the Linux XSD,
             and the fields a Linux module needs that the Windows file does not carry.
  --emit DIR write a neutral JSON model (init/stream/hold sequences, modes, power sequences)
             and re-read it as a round-trip check. The model carries Windows register data (S5):
             DIR must be outside git or git-ignored (use out/firmware-private/cameras/camx/).
  --emit-v7  refused (exit 2): the V7 writer is blocked, reasons are printed.

Logging is structure only: counts, names of enumerators, sizes. No register address, value,
voltage or I2C address is printed.

    python3 -I convert-surface-module.py                       # report for all three sensors
    python3 -I convert-surface-module.py rear --emit ../../../../out/firmware-private/cameras/camx
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
READER = os.path.join(REPO, "hardware", "cameras", "userspace", "parse-camera-module.py")
LINUX_DIR_DEFAULT = os.path.join(
    REPO, "out", "ref", "camx-hamoa", "pkg", "camx-hamoa-1.0.56", "camx-hamoa", "arm64", "usr", "lib",
    "aarch64-linux-gnu", "camx", "hamoa", "camera")

# Enumerators of the Linux XSD (camxsensordriver.xsd, section 4 of any V7 module); read from the data.
POWER_ENUM = ["MCLK", "VANA", "VDIG", "VIO", "VAF", "VAF_PWDN", "CUSTOM_REG1", "CUSTOM_REG2", "RESET",
              "STANDBY", "CUSTOM_GPIO1", "CUSTOM_GPIO2", "VANA1"]
OP_ENUM = ["WRITE", "WRITE_BURST", "WRITE_SEQUENTIAL", "READ", "POLL", "READ_APPEND_WRITE",
           "SEQUENTIAL_XFER_LOCK", "SEQUENTIAL_XFER_UNLOCK"]
POWER_UP_ROOT, POWER_DOWN_ROOT = 0x48, 0x50  # (count, powerSetting symbol) pairs in sensorDriverData
LINUX_NAMES = {"rear": "ov13858", "front": "imx681", "ir": "vd55g0"}
# Fields the Linux slaveInfo needs and the Windows module cannot supply (Verified by the symbol names).
LINUX_ONLY_SLAVEINFO = ["sensorLibName", "slaveAddress", "regAddrType", "regDataType", "sensorIdRegAddr",
                        "sensorId", "sensorIdMask", "sensorGmslRealProbeInfo", "sensorRegBankUnlockInfo",
                        "sensorRegBankLockInfo", "moduleType"]


def load_reader():
    spec = importlib.util.spec_from_file_location("parse_camera_module", READER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pcm = load_reader()


class V7(object):
    """Structure-only reader of a Parameter Parser V7.x container (Qualcomm Linux package)."""

    def __init__(self, path):
        b = self.b = open(path, "rb").read()
        self.path = path
        if b[:20] != b"QTI Chromatix Header":
            raise ValueError("not a QTI Chromatix file")
        u = lambda o: struct.unpack_from("<I", b, o)[0]
        self.version = (u(0x20), u(0x24))
        self.parser = b[0x28:0x58].split(b"\0")[0].decode("latin1")
        self.name = b[0x58:0x98].split(b"\0")[0].decode("latin1")
        n = u(0xA4)
        if not 1 <= n <= 16:
            raise ValueError("section count")
        self.secs = {}
        self.order = []
        for i in range(n):
            sid, off, size = struct.unpack_from("<III", b, u(0xA0) + 12 * i)
            if off + size > len(b):
                raise ValueError("section outside file")
            self.secs[sid] = (off, size)
            self.order.append(sid)
        self.tail = b[-8:]
        self.size_field = u(0x1C)

    def sec(self, sid):
        off, size = self.secs[sid]
        return self.b[off:off + size]

    def xsd_tokens(self):
        if 4 not in self.secs:
            return set()
        return set(m.group().decode() for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{1,}", self.sec(4)))

    def enum(self, type_name):
        toks = [m.group().decode() for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]{1,}", self.sec(4))]
        i = toks.index(type_name)
        return toks[i + 1:i + 40]


def find_windows(winroot, sensor):
    pkg, fn, _, _ = pcm.SENSORS[sensor]
    hits = glob.glob(os.path.join(winroot, "DriverStore", pkg, fn))
    if len(hits) != 1:
        raise SystemExit("cannot find %s (%d hits)" % (fn, len(hits)))
    return hits[0]


def power_sequences(mod):
    root = mod.root()
    out = {}
    for key, off in (("up", POWER_UP_ROOT), ("down", POWER_DOWN_ROOT)):
        cnt, sym = struct.unpack_from("<II", root, off)
        s = mod.sym(sym)
        if s["name"] != "powerSetting" or s["dsz"] != 12 * cnt:
            raise pcm.FormatError("power sequence layout at root 0x%x" % off)
        d = mod.data(sym)
        out[key] = [dict(type=struct.unpack_from("<I", d, 12 * i)[0],
                         value=struct.unpack_from("<I", d, 12 * i + 4)[0],
                         delay_ms=struct.unpack_from("<I", d, 12 * i + 8)[0]) for i in range(cnt)]
    return out


def build_model(mod, sensor):
    seq = {k: mod.sequence(k) for k in pcm.SEQ_ORDER}
    modes = mod.modes()
    name = mod.named("sensorName")[0]
    return dict(
        format="SPCAMXMODEL", version=1, sensor=sensor, linux_name=LINUX_NAMES[sensor],
        windows_module=mod.name, windows_parser=mod.parser, cfa_code=modes[0]["cfa"],
        sequences=seq, power=power_sequences(mod),
        modes=[{k: v for k, v in m.items()} for m in modes],
        sensor_name=mod.data(name["idx"]).split(b"\0")[0].decode("latin1"))


def digest(model):
    h = hashlib.sha256()
    for k in pcm.SEQ_ORDER:
        for r in model["sequences"][k]:
            h.update(json.dumps(r, sort_keys=True).encode())
    for m in model["modes"]:
        for r in m["records"]:
            h.update(json.dumps(r, sort_keys=True).encode())
    h.update(json.dumps(model["power"], sort_keys=True).encode())
    return h.hexdigest()


def report(sensor, wmod, linux_dir):
    print("== %s (%s)" % (sensor, LINUX_NAMES[sensor]))
    print("  windows: container words %s, parser '%s', sections %s, symbols %d (%d distinct names), CRC-32 ok"
          % (wmod.version_words, wmod.parser, [s[0] for s in wmod.secs], len(wmod.syms),
             len(set(s["name"] for s in wmod.syms))))
    files = sorted(glob.glob(os.path.join(linux_dir, "com.qti.sensormodule.*.bin")))
    if not files:
        print("  linux: no package modules under %s" % linux_dir)
        return
    wnames = set(s["name"] for s in wmod.syms)
    for f in files:
        v = V7(f)
        tok = v.xsd_tokens()
        print("  linux %-44s words %s parser '%s' sections %s (sizes %s) xsd tokens %d, windows names covered %d/%d"
              % (os.path.basename(f), v.version, v.parser.split(" (")[0], v.order,
                 [v.secs[i][1] for i in v.order], len(tok), len(wnames & tok), len(wnames)))
    ref = V7(files[0])
    tok = ref.xsd_tokens()
    print("  windows-only names (schema drift): %s" % sorted(wnames - tok))
    print("  linux slaveInfo fields absent in the windows module: %s" % [n for n in LINUX_ONLY_SLAVEINFO if n not in wnames])
    print("  windows power enumerators map to the linux XSD enumerators: %s"
          % ("yes" if ref.enum("PowerConfigurationType")[:len(POWER_ENUM)] == POWER_ENUM else "NO"))
    pw = power_sequences(wmod)
    for k in ("up", "down"):
        print("  power %s: %d steps, types %s" % (k, len(pw[k]), [POWER_ENUM[s["type"]] for s in pw[k]]))
    ops = sorted(set(r["op"] for k in pcm.SEQ_ORDER for r in wmod.sequence(k)) |
                 set(r["op"] for m in wmod.modes() for r in m["records"]))
    print("  register operations used: %s (identical numbering in the linux OperationType enum)"
          % [OP_ENUM[o] for o in ops])


def emit(model, outdir):
    path = os.path.join(outdir, "%s.camxmodel.json" % model["linux_name"])
    with open(path, "w") as fh:
        json.dump(model, fh, sort_keys=True)
    os.chmod(path, 0o600)
    back = json.load(open(path))
    ok = digest(back) == digest(model) and back["modes"].__len__() == len(model["modes"])
    print("  emitted %s (%d bytes); round-trip digest %s" % (path, os.path.getsize(path), "ok" if ok else "MISMATCH"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sensors", nargs="*", help="rear, front, ir (default: all)")
    ap.add_argument("--windows-dir", default=os.path.join(REPO, "sources", "windows"))
    ap.add_argument("--linux-dir", default=LINUX_DIR_DEFAULT)
    ap.add_argument("--emit", metavar="DIR")
    ap.add_argument("--emit-v7", action="store_true")
    a = ap.parse_args()
    if a.emit_v7:
        print("refused: the V7.4.1 writer is blocked.\n"
              " 1. type and field names are stored as 64-bit hashes whose function is not known;\n"
              " 2. the 8-byte trailer is not CRC-32/CRC-64 over any section range (tried standard variants);\n"
              " 3. the HAL checks per-type name hash, version and structure byte counts against its own XSD;\n"
              " 4. the sensor library (com.qti.sensor.<name>.so) for imx681 and vd55g0 does not exist.\n"
              "See the evidence file, section 4.")
        return 2
    outdir = None
    if a.emit:
        outdir = pcm.check_emit_dir(a.emit)
        os.makedirs(outdir, mode=0o700, exist_ok=True)
    rc = 0
    for s in (a.sensors or list(pcm.SENSORS)):
        if s not in pcm.SENSORS:
            ap.error("unknown sensor %s" % s)
        try:
            mod = pcm.Module(find_windows(a.windows_dir, s))
            report(s, mod, a.linux_dir)
            if outdir and not emit(build_model(mod, s), outdir):
                rc = 1
        except (pcm.FormatError, ValueError) as e:
            print("== %s: ERROR %s" % (s, e))
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
