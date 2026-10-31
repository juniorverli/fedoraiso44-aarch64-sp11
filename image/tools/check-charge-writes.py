#!/usr/bin/env python3
"""S6 fail-closed text audit: any non-comment charge_control_* reference needs an audited read.

ELF/package code may implement threshold APIs; D23 separately prevents the driver exposing
these attributes from loading. This audit prevents image configuration, scripts and rules
from calling them, including a path assigned to a variable and written on another line.
"""
import hashlib
import os
from pathlib import Path
import re
import sys

# Audited DSP drop-in reads thresholds through R() -> timeout cat; never writes sysfs.
# M13: re-audited; the owner file (6a7d69f) plus the image append still has exactly one charge_control_ reference, the attribute
# list of the power_supply read loop (R() = timeout cat), and no redirection into /sys.
# M14: re-audited after the DSP collector refresh (owner file plus the image append): still exactly one charge_control_ reference, the
# attribute list of the power_supply read loop through R() = timeout cat. The power-thermal collector (owner file) has one
# charge_control_ glob that is only listed with stat and read through rdl() = timeout cat; no write to /sys anywhere.
DSP_SHA256 = "95acaf2950b7b2be3faeaf44710e52f98479b38c9077b9dc09f4ca899ca8838b"
POWER_THERMAL_SHA256 = "e7486972bebf1ade4e309cd637f74f385a8d24e620801f2d3d3d7d59a2e72c1c"

def audit(root):
    failures = []
    checked = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        rel = Path(directory).relative_to(root)
        if str(rel) in ("proc", "sys", "dev", "usr/lib/firmware", "usr/lib/modules",
                        "usr/share/doc", "usr/share/licenses", "usr/share/man"):
            dirs[:] = []
            continue
        for name in files:
            p = Path(directory) / name
            if p.is_symlink() or not p.is_file():
                continue
            # Search bytes in chunks to avoid loading large files; binary files do not
            # contain executable shell/udev policy. Never print the file's contents (S5).
            with p.open("rb") as f:
                first = f.read(65536)
                if b"\0" in first:
                    continue
                data = first
                while b"charge_control_" not in data:
                    more = f.read(65536)
                    if not more:
                        break
                    data = data[-32:] + more
                else:
                    f.seek(0)
                    data = f.read()
            if b"charge_control_" not in data:
                continue
            checked += 1
            audited = {"etc/sp11-log-collector.d/dsp-subsystems.sh": DSP_SHA256, "etc/sp11-log-collector.d/power-thermal.sh": POWER_THERMAL_SHA256}
            if audited.get(str(p.relative_to(root))) == hashlib.sha256(data).hexdigest():
                continue
            for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                if "charge_control_" not in line or line.lstrip().startswith("#"):
                    continue
                # Fedora UPower rules test for the attribute; TEST is not an ATTR write.
                if re.fullmatch(r'\s*SUBSYSTEM=="power_supply", TEST=="charge_control_(start|end)_threshold", \\', line):
                    continue
                failures.append(f"{p.relative_to(root)}:{number}: unapproved charge-control reference")
    return checked, failures

if __name__ == "__main__":
    count, errors = audit(Path(sys.argv[1]))
    print("\n".join(errors) if errors else f"PASS: {count} files with charge-control references audited")
    sys.exit(bool(errors))
