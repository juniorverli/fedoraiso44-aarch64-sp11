#!/usr/bin/env python3
"""Check explicit VI-only generation and its fail-closed CPS policy."""
import argparse
import hashlib
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
GEN = HERE / "sp11_closedloop.py"
CARD = "X1E80100-Microsoft-Surface-Pro-11"
sys.path.insert(0, str(HERE.parent))
import acdb_inspect  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--acdb", type=Path, required=True)
    ap.add_argument("--staged-calibration", type=Path)
    args = ap.parse_args()
    acdb = acdb_inspect.Acdb(args.acdb.read_bytes())
    maps = [data for iid, pid, data in acdb.calibration_payloads({0x4024})
            if pid == 0x08001203]
    assert len(maps) == 1 and len(maps[0]) == 20
    assert struct.unpack("<5I", maps[0]) == (4, 1, 2, 3, 4)
    with tempfile.TemporaryDirectory(prefix="sp11-gen-host-") as tmp:
        base = ["python3", "-I", str(GEN), "--acdb", str(args.acdb), "--out-dir", tmp]
        for extra in ([], ["--with-cps"], ["--vi-only-diagnostic", "--measured", "4", "4", "25", "25"]):
            run = subprocess.run(base + extra, capture_output=True, text=True)
            assert run.returncode != 0 and not list(Path(tmp).rglob("*.bin")), run.stderr
        run = subprocess.run(base + ["--vi-only-diagnostic", "--nominal-cal", "--self-test"],
                             capture_output=True, text=True, check=True)
        assert "CPS chain absent, muted diagnostic only" in run.stdout
        fw = Path(tmp) / "qcom/x1e80100"
        supplement = (fw / f"{CARD}-sp11cl.bin").read_bytes()
        cal = (fw / f"{CARD}-sp11cal.bin").read_bytes()
        assert supplement[:8] == b"SP11CL01"
        links, records, flags = struct.unpack_from("<3I", supplement, 8)
        assert (links, records, flags) == (1, 28, 1)
        assert len(cal) == 36 and cal[:8] == b"SP11CA01"
        assert struct.unpack_from("<2I", cal, 8) == (1, 2)
        if args.staged_calibration:
            assert hashlib.sha256(cal).digest() == hashlib.sha256(args.staged_calibration.read_bytes()).digest()
        run = subprocess.run(base + ["--vi-only-diagnostic"], capture_output=True, text=True)
        assert run.returncode != 0 and "stale calibration" in run.stderr
        assert (fw / f"{CARD}-sp11cl.bin").read_bytes() == supplement
    print("PASS: implicit CPS omission, unimplemented CPS and measured generation are rejected")
    print("PASS: explicit VI diagnostic has one link, CPS-required guard flag and 36-byte nominal calibration")
    print("PASS: generation without calibration refuses a stale file before writing")
    print("PASS: keyless ACDB VI map has four entries [1, 2, 3, 4]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
