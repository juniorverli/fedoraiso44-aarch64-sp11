#!/usr/bin/env python3
"""Check every file listed in DriverStore/*.ini against its catalog hash.

Non-PE files match a plain SHA-1. PE files (.sys, .dll, .exe) match the
Authenticode SHA-1, which skips the checksum, the certificate-table
directory entry and the certificate data.

Usage: python3 -I scripts/verify-driverstore.py <DriverStore>
Exit status 0 when every listed file that exists matches.
"""
import glob
import hashlib
import os
import struct
import sys


def authenticode_sha1(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    checksum = opt + 64
    dirs = opt + (96 if magic == 0x10B else 112)
    sec = dirs + 8 * 4
    va, _ = struct.unpack_from("<II", data, sec)
    h = hashlib.sha1()
    h.update(data[:checksum])
    h.update(data[checksum + 4:sec])
    h.update(data[sec + 8:va if va else len(data)])
    return h.hexdigest()


def main(store):
    ok = bad = missing = 0
    for ini in sorted(glob.glob(os.path.join(store, "*.ini"))):
        pkg = ini[:-4]
        if not os.path.isdir(pkg):
            continue
        lines = open(ini, errors="ignore").read().splitlines()
        if "[Files]" not in lines:
            continue
        for line in lines[lines.index("[Files]") + 1:]:
            if "=" not in line:
                continue
            name, rest = line.split("=", 1)
            want = rest.split(",")[-1].strip().lower()
            path = os.path.join(pkg, *name.split("\\"))
            if not os.path.exists(path):
                missing += 1
                print("MISSING", path)
                continue
            data = open(path, "rb").read()
            if hashlib.sha1(data).hexdigest() == want:
                ok += 1
                continue
            try:
                got = authenticode_sha1(data)
            except (struct.error, ValueError):
                got = None
            if got == want:
                ok += 1
            else:
                bad += 1
                print("MISMATCH", path)
    print(f"ok {ok} mismatch {bad} missing {missing}")
    return 0 if bad == 0 and missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
