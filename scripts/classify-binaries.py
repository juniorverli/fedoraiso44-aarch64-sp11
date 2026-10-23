#!/usr/bin/env python3
"""Classify every file of the Windows dumps by its real format, from its bytes.

The goal is that no agent ever guesses an architecture or a format from a file
extension. Each row says what the file is (container), which CPU its code is
for (machine), whether it is code or data, and which Ghidra language to load it
with -- or that it must not be disassembled at all.

  python3 -I scripts/classify-binaries.py sources/windows sources/binary-catalog.tsv

Columns: path, size, sha256, container, machine, kind, ghidra_language,
entropy, details, magic.
"""
import hashlib
import json
import math
import os
import struct
import sys

PE_MACHINES = {
    0x014C: "x86", 0x8664: "x64", 0xAA64: "ARM64", 0xA641: "ARM64EC",
    0xA64E: "ARM64X", 0x01C4: "ARMv7 Thumb-2", 0x01C0: "ARM",
}
ELF_MACHINES = {
    0: "none", 3: "x86", 40: "ARM", 62: "x64", 94: "Xtensa",
    164: "Hexagon (QDSP6)", 183: "ARM64",
}
GHIDRA = {
    "x86": "x86:LE:32:default", "x64": "x86:LE:64:default",
    "ARM64": "AARCH64:LE:64:v8A", "ARM64X": "AARCH64:LE:64:v8A",
    "ARM64EC": "AARCH64:LE:64:v8A", "ARM": "ARM:LE:32:v8",
    "ARMv7 Thumb-2": "ARM:LE:32:v8", "Xtensa": "Xtensa:LE:32:default",
    "Hexagon (QDSP6)": "Hexagon:LE:32:default",
}
PE_SUBSYSTEMS = {1: "native", 2: "windows-gui", 3: "windows-cui", 10: "efi-app",
                 11: "efi-boot-driver", 12: "efi-runtime-driver"}
# Files whose ELF header misleads. Matched by file name. Each entry was checked
# by hand on 2026-10-24 (program headers and segment bytes); grade in the note.
OVERRIDES = {
    "qcdxkmsuc8380.mbn": ("gpu-firmware", "none (not Hexagon code: do not disassemble)",
        "Adreno zap shader in a signed PIL ELF; e_machine 164 is the container convention, "
        "the 0x430-byte segment is GPU code for TrustZone to load (Inference)"),
    "qcdxkmsucpurwa.mbn": ("gpu-firmware", "none (not Hexagon code: do not disassemble)",
        "Adreno zap shader for the Purwa SoC, not this one (Inference)"),
    "adsp_dtbs.elf": ("data", "none (not code: do not disassemble)",
        "DSP device-tree container in a signed PIL ELF; segment starts with 'CFGL', holds FDTs "
        "(Verified: FDT magic present); e_machine 1 is meaningless here"),
    "cdsp_dtbs.elf": ("data", "none (not code: do not disassemble)",
        "DSP device-tree container in a signed PIL ELF; segment starts with 'CFGL', holds FDTs "
        "(Verified: FDT magic present); e_machine 1 is meaningless here"),
    "phy_ucode20.elf": ("code", "NO GHIDRA LANGUAGE: e_machine 3 (x86) is implausible for WCN7850 PHY microcode, do not guess",
        "Wi-Fi PHY microcode; the declared CPU is not trusted (Hypothesis)"),
    "qcav1e8380.mbn": ("code", "NO GHIDRA LANGUAGE: unknown core (e_machine 106), do not guess",
        "AV1 encoder firmware; the CPU core is unidentified (TBD)"),
}

FMP_CAPSULE_GUID = bytes.fromhex("edd5cb6d2de8444cbda17194199ad92a")
EFI_CAPSULE_GUIDS = {FMP_CAPSULE_GUID: "UEFI FMP capsule"}


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in counts if c)


def rva_to_off(data, sections, rva):
    for va, vsize, raw, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return raw + (rva - va)
    return None


def pe_info(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return None
    machine, nsec = struct.unpack_from("<HH", data, pe + 4)
    opt_size, chars = struct.unpack_from("<HH", data, pe + 20)
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    is64 = magic == 0x20B
    subsystem = struct.unpack_from("<H", data, opt + 68)[0]
    dirs = opt + (112 if is64 else 96)
    ndirs = struct.unpack_from("<I", data, dirs - 4)[0]
    sec = opt + opt_size
    sections = []
    for i in range(nsec):
        s = sec + 40 * i
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, s + 8)
        sections.append((va, vsize, raw, rawsize))
    name = PE_MACHINES.get(machine, f"pe-machine-0x{machine:04x}")
    details = [("dll" if chars & 0x2000 else "exe"), PE_SUBSYSTEMS.get(subsystem, f"subsystem-{subsystem}")]
    if ndirs > 14 and struct.unpack_from("<II", data, dirs + 14 * 8)[1]:
        details.append(".NET")
    # Hybrid images: a CHPE metadata pointer in the load config marks ARM64X
    # (machine ARM64) or CHPE x86 (machine x86, with ARM64 code inside).
    if ndirs > 10:
        lc_rva, lc_size = struct.unpack_from("<II", data, dirs + 10 * 8)
        off = rva_to_off(data, sections, lc_rva) if lc_rva else None
        field = 0xC8 if is64 else 0x7C
        if off is not None and off + 4 <= len(data):
            size = struct.unpack_from("<I", data, off)[0]
            if size >= field + (8 if is64 else 4) and off + field + 8 <= len(data):
                ptr = struct.unpack_from("<Q" if is64 else "<I", data, off + field)[0]
                if ptr:
                    if machine == 0xAA64:
                        name = "ARM64X"
                        details.append("hybrid ARM64 + ARM64EC/x64 code")
                    elif machine == 0x014C:
                        name = "x86"
                        details.append("CHPE: x86 with embedded ARM64 code")
    return name, details


def elf_info(data):
    cls, endian = data[4], data[5]
    e = "<" if endian == 1 else ">"
    etype, emachine = struct.unpack_from(e + "HH", data, 16)
    if cls == 1:
        flags = struct.unpack_from(e + "I", data, 36)[0]
        phoff = struct.unpack_from(e + "I", data, 28)[0]
        phentsize, phnum = struct.unpack_from(e + "HH", data, 42)
    else:
        flags = struct.unpack_from(e + "I", data, 48)[0]
        phoff = struct.unpack_from(e + "Q", data, 32)[0]
        phentsize, phnum = struct.unpack_from(e + "HH", data, 54)
    name = ELF_MACHINES.get(emachine, f"elf-machine-{emachine}")
    details = [f"ELF{32 if cls == 1 else 64}{'LE' if endian == 1 else 'BE'}",
               {1: "rel", 2: "exec", 3: "dyn", 4: "core"}.get(etype, f"type-{etype}")]
    if emachine == 164:
        details.append(f"hexagon-arch v{flags & 0xff:x}")
    hash_seg = False
    loads = 0
    exec_segs = 0
    for i in range(phnum):
        p = phoff + i * phentsize
        if p + phentsize > len(data):
            break
        if cls == 1:
            ptype, _, _, _, _, _, pflags, _ = struct.unpack_from(e + "IIIIIIII", data, p)
        else:
            ptype, pflags = struct.unpack_from(e + "II", data, p)
        if ptype == 1:
            loads += 1
            if pflags & 0x1:
                exec_segs += 1
        if (pflags >> 24) & 0x7 == 0x2:
            hash_seg = True
    details.append(f"{phnum} phdrs, {loads} PT_LOAD, {exec_segs} executable")
    if hash_seg:
        details.append("Qualcomm signed image (hash segment)")
    if b"\xd0\x0d\xfe\xed" in data:
        details.append("contains a flattened device tree")
    return name, details, hash_seg, exec_segs


def text_kind(data):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "text (UTF-16)"
    sample = data[:4096]
    printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in sample)
    if sample and printable / len(sample) > 0.97:
        s = sample.lstrip()
        if s.startswith(b"<"):
            return "XML"
        if all(c in b"0123456789abcdefABCDEF \r\n\t" for c in s[:512]):
            return "hex text"
        return "text"
    return None


def classify(path):
    data = open(path, "rb").read()
    ext = os.path.splitext(path)[1].lower()
    ent = entropy(data[:1 << 20])
    magic = data[:8].hex()
    container = machine = kind = lang = ""
    details = []
    if data[:2] == b"MZ" and len(data) > 0x40:
        info = pe_info(data)
        if info:
            container, (machine, details) = "PE", info
            kind = "code"
            lang = GHIDRA.get(machine, "TBD")
    if not container and data[:4] == b"\x7fELF":
        machine, details, signed, exec_segs = elf_info(data)
        container = "ELF (Qualcomm MBN)" if signed else "ELF"
        # e_machine alone is not proof of code: board data and DT blobs are
        # shipped as ELF with a CPU set but no executable segment.
        kind = "code" if exec_segs else "data-in-ELF"
        lang = GHIDRA.get(machine, "NO GHIDRA LANGUAGE: unknown core, do not guess") if kind == "code" else "none"
    if not container:
        if data[:4] == b"\xd0\x0d\xfe\xed":
            container, kind = "flattened device tree", "data"
        elif data[:2] == b"\x1f\x8b":
            container, kind = "gzip", "compressed"
        elif data[:6] == b"\xfd7zXZ\x00":
            container, kind = "xz", "compressed"
        elif data[:4] == b"PK\x03\x04":
            container, kind = "zip", "compressed"
        elif data[:4] == b"MSCF":
            container, kind = "cab", "compressed"
        elif data[:16] in EFI_CAPSULE_GUIDS:
            container, kind = EFI_CAPSULE_GUIDS[data[:16]], "firmware-capsule"
        elif data[:2] == b"\x30\x82" and b"\x2a\x86\x48\x86\xf7\x0d\x01\x07\x02" in data[:64]:
            container, kind = "PKCS#7 signed data (catalog)", "signature"
        elif ext in (".json", ".jsn"):
            try:
                json.loads(data.decode("utf-8-sig"))
                container, kind = "JSON", "config"
            except (ValueError, UnicodeDecodeError):
                container, kind = "JSON (invalid)", "config"
        else:
            t = text_kind(data)
            if t:
                container, kind = t, "text"
            else:
                container, kind = "opaque blob", "data"
                details.append("high entropy: compressed or encrypted" if ent > 7.9 else
                               "structured binary data")
        lang = "none"
    if kind != "code":
        lang = "none (not code: do not disassemble)"
    base = os.path.basename(path)
    if base in OVERRIDES:
        kind, lang, note = OVERRIDES[base]
        details.append("OVERRIDE: " + note)
    return {
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "container": container, "machine": machine or "-", "kind": kind,
        "ghidra_language": lang, "entropy": f"{ent:.2f}",
        "details": "; ".join(details), "magic": magic,
    }


def main(root, out):
    cols = ["path", "size", "sha256", "container", "machine", "kind",
            "ghidra_language", "entropy", "details", "magic"]
    rows = []
    for top in ("DriverStore", "Firmware", "System32_drivers", "live-inventory"):
        for dirpath, _, files in os.walk(os.path.join(root, top)):
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                if os.path.islink(p):
                    continue
                r = classify(p)
                r["path"] = os.path.relpath(p, root)
                rows.append(r)
    rows.sort(key=lambda r: r["path"])
    with open(out, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")
    print(f"{len(rows)} files -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
