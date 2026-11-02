#!/usr/bin/env python3
"""Verify the locally extracted, pinned public reference inputs."""
import hashlib
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
with (ROOT / "sources/sources.toml").open("rb") as stream:
    pins = tomllib.load(stream)

errors = 0
count = 0
for name in ("reference_linux_sp11", "reference_archlinux_repo", "reference_audioreach_topology"):
    section = pins[name]
    for relative, expected in section["sha256"].items():
        path = ROOT / section["path"] / relative
        try:
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError as exc:
            print(f"MISSING {path}: {exc}", file=sys.stderr)
            errors += 1
            continue
        count += 1
        if actual != expected:
            print(f"MISMATCH {path}: expected {expected}, got {actual}", file=sys.stderr)
            errors += 1
print(f"Checked {count} files; {errors} errors")
sys.exit(bool(errors))
